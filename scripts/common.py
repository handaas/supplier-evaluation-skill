#!/usr/bin/env python3
"""Shared helpers for the enterprise-fusion-skill."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, List, Optional

DOMAIN = "fusion"
DOMAIN_UPPER = "FUSION"
REPORT_BANNER = "供应商评估"
REPORT_TYPE = "supplier_report"


class QualityGateError(RuntimeError):
    """Raised when quality gate check fails (e.g. all dimensions empty)."""
    pass


def json_dumps(value: Any, *, pretty: bool = False) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":"))


def print_json(value: Any) -> None:
    print(json_dumps(value, pretty=True))


def _pagination_total(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 and value.is_integer() else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def collect_detail_pages(
    call: Callable[[str, Dict[str, Any]], Any],
    tool: str,
    arguments: Dict[str, Any],
    *,
    get_rows: Callable[[Any], List[Any]],
    get_total: Callable[[Any], Any],
    is_error: Callable[[Any], bool],
    max_pages: Optional[int] = 1,
    sample_size: Optional[int] = None,
    matches: Optional[Callable[[Any], bool]] = None,
    page_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Calculate total-driven quantities within an explicit paid-page budget; default to one page."""
    size = page_size if page_size is not None else arguments.get("pageSize")
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError("明细分页必须提供正整数 pageSize 或已确认的接口固定页大小")
    if max_pages is not None and (isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1):
        raise ValueError("max_pages 必须为正整数或 None")
    if sample_size is not None and (isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 1):
        raise ValueError("sample_size 必须为正整数或 None")
    rows: List[Any] = []
    seen_pages: Dict[str, int] = {}
    first_payload: Any = None
    total = latest_total = None
    fetched = accepted = matched = pages = succeeded = 0
    reason = "max_pages"
    failed_page = repeated_from_page = None
    page_index = 1
    while max_pages is None or page_index <= max_pages:
        payload = call(tool, {**arguments, "pageIndex": page_index})
        pages += 1
        if first_payload is None:
            first_payload = payload
        if is_error(payload):
            reason, failed_page = "error", page_index
            break
        page_rows = get_rows(payload)
        fetched += len(page_rows)
        latest_total = _pagination_total(get_total(payload))
        if total is None:
            total = latest_total
        elif latest_total is not None and latest_total != total:
            reason = "total_changed"
            break
        if page_rows:
            fingerprint = hashlib.sha256(json.dumps(page_rows, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
            if fingerprint in seen_pages:
                reason, repeated_from_page = "repeated_page", seen_pages[fingerprint]
                break
            seen_pages[fingerprint] = page_index
        accepted += len(page_rows)
        succeeded += 1
        for row in page_rows:
            rows.append(row)
            if matches is None or matches(row):
                matched += 1
            if sample_size is not None and matched >= sample_size:
                break
        if latest_total is None:
            reason = "missing_total"
            break
        if accepted > total:
            reason = "count_mismatch"
            break
        if sample_size is not None and matched >= sample_size:
            reason = "target_reached"
            break
        if accepted == total:
            reason = "total_exhausted"
            break
        if not page_rows:
            reason = "empty_page"
            break
        page_index += 1
    complete = total is not None and len(rows) == total and reason in ("total_exhausted", "target_reached")
    unfetched = max(total - accepted, 0) if total is not None else None
    info = {
        "sample_size": sample_size, "page_size": size, "max_pages": max_pages,
        "call_budget": max_pages,
        "estimated_calls": min(max(1, (total + size - 1) // size), max_pages) if total is not None and max_pages is not None else None,
        "collection_mode": "sample" if sample_size is not None else "coverage",
        "upstream_total": total, "latest_total": latest_total,
        "total_pages": (total + size - 1) // size if total is not None else None,
        "pages_fetched": pages, "pages_succeeded": succeeded,
        "rows_fetched": fetched, "rows_accepted": accepted, "rows_scanned": len(rows),
        "sample_count": matched,
        "remaining_rows": max(total - len(rows), 0) if total is not None else None,
        "unfetched_rows": unfetched,
        "remaining_pages": (unfetched + size - 1) // size if unfetched is not None else None,
        "source_exhausted": complete, "stop_reason": reason,
        "failed_page": failed_page, "repeated_from_page": repeated_from_page,
    }
    result = dict(first_payload) if isinstance(first_payload, dict) else {}
    if reason == "error" and not rows:
        result = {"_error": "明细接口调用失败"}
    result.update(resultList=rows, _pagination=info)
    if total is not None:
        result["total"] = total
    return result


def attach_pagination(report: Dict[str, Any], sources: Dict[str, Any]) -> Dict[str, Any]:
    """Expose per-interface totals and incomplete collection in every report format."""
    pagination = {label: payload["_pagination"] for label, payload in sources.items()
                  if isinstance(payload, dict) and isinstance(payload.get("_pagination"), dict)}
    if not pagination:
        return report
    report.setdefault("data_source", {})["pagination"] = pagination
    disclosures = []
    for label, info in pagination.items():
        total = info["upstream_total"]
        expected = info["total_pages"]
        disclosure = f"{label}：上游 total={total if total is not None else '未返回有效总量'}"
        if expected is not None:
            disclosure += f"，按单页 {info['page_size']} 条预计 {expected} 页"
        disclosure += f"，实际请求 {info['pages_fetched']} 页、取得 {info['rows_scanned']} 条"
        if info["remaining_rows"] is not None:
            disclosure += f"，未纳入 {info['remaining_rows']} 条"
        disclosure += f"；{'已完整采集' if info['source_exhausted'] else '采集不完整'}，停止原因 {info['stop_reason']}。"
        disclosures.append(disclosure)
    text = "".join(disclosures)
    if any(not info["source_exhausted"] for info in pagination.values()):
        for key in ("abstract", "summary"):
            report[key] = str(report.get(key) or "") + "明细含未完整采集的来源，数量与范围详见查询口径；不能据此推断总体。"
    caliber = report.setdefault("caliber", {})
    caliber["limit"] = str(caliber.get("limit") or "") + text
    return report
