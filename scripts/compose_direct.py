#!/usr/bin/env python3
"""Direct multi-MCP composition for the supplier-evaluation report.

Connects to 6 MCP servers (or reads cached reports for dry-run), runs
cross-domain analysis, and assembles a rich report payload that no single
atomic skill can produce — including cross-dimensional insights, a specialty
score matrix, and a structured verdict.

Output payload follows the unified JSON skeleton so render_report.py renders it
unchanged.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import sys
from typing import Any, Dict, List, Mapping, Optional

import mcp_orchestration as orch
import cross_analysis as xa
from cross_analysis import (
    _pick,
    _i,
    _base,
    _risk,
    _operation,
    _channel,
    _factory,
    _recruitment,
    _investments,
)

REPORT_TYPE = "supplier_evaluation_direct"
BANNER = "供应商评估报告"

# --------------------------------------------------------------------------- #
# Per-domain detail extractors
# --------------------------------------------------------------------------- #
_BASE_FIELDS = [
    ("企业名称", ("企业名称", "name", "名称")),
    (
        "统一社会信用代码",
        ("统一社会信用代码", "socialCreditCode", "scCode", "信用代码"),
    ),
    ("法定代表人", ("法定代表人", "legalRepresentative", "法人代表")),
    ("企业类型", ("企业类型", "enterpriseType")),
    ("行业", ("行业", "industry", "industryName")),
    ("注册资本", ("注册资本", "regCapital", "regCapitalValue")),
    ("实缴资本", ("实缴资本", "realCapital", "paidInCapital")),
    ("成立日期", ("成立日期", "foundTime", "成立时间")),
    ("经营状态", ("经营状态", "operStatus")),
    ("注册地址", ("注册地址", "address", "addressValue")),
    ("经营范围", ("经营范围", "businessScope")),
]


def _base_kv(data: Mapping[str, Any]) -> Dict[str, str]:
    base = _base(data)
    out: Dict[str, str] = {}
    for label, keys in _BASE_FIELDS:
        v = _pick(base, *keys)
        if v not in (None, "", "-"):
            out[label] = str(v)
    # also surface paid-in rate if present in the cached-report base
    rate = _pick(base, "资本实缴率", "实缴率")
    if rate:
        out["资本实缴率"] = str(rate)
    return out


_RISK_DIMS = [
    ("行政处罚", "penalties"),
    ("经营异常", "anomalies"),
    ("限制高消费", "restrictions"),
    ("开庭公告", "court_hearings"),
    ("动产抵押", "mortgages"),
    ("严重违法", "serious_violations"),
    ("知识产权出质", "ip_pledge"),
]


def _risk_dim_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    risk = _risk(data)
    rows = []
    for label, key in _RISK_DIMS:
        val = risk.get(key)
        if val:
            # 优先用 MCP total，回退到 list 长度
            total_key = key + "_total"
            count = risk.get(total_key) or len(val) if isinstance(val, list) else 1
            rows.append({"风险维度": label, "记录数": str(count)})
    return rows


def _hearing_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Court hearing detail records."""
    rows = []
    for h in (_risk(data).get("court_hearings") or [])[:20]:
        if not isinstance(h, dict):
            continue
        case_no = _pick(h, "caseNo", "caseNumber", "caCaseNo", "案号")
        hearing_date = _pick(
            h,
            "hearingDate",
            "courtTime",
            "startDate",
            "publishDate",
            "noticeDate",
            "开庭日期",
            "发布日期",
        )
        rows.append(
            {
                "案号": str(case_no or "-"),
                "案由": str(_pick(h, "case_reason", "caseReason", "案由") or "-"),
                "法院": str(_pick(h, "publishUnit", "court", "法院") or "-"),
                "相关主体": str(
                    _pick(
                        h,
                        "enterpriseName",
                        "partyName",
                        "relatedEntity",
                        "当事人",
                        "相关主体",
                    )
                    or "-"
                ),
                "开庭/发布日期": str(hearing_date or "-"),
                "公告类型": str(_pick(h, "caseType", "公告类型") or "开庭公告"),
                "去重键状态": (
                    "案号+日期可用"
                    if case_no and hearing_date
                    else "缺少案号或日期，无法逐案去重"
                ),
            }
        )
    return rows


def _restriction_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Consumption restriction (限高) detail records."""
    rows = []
    for r in (_risk(data).get("restrictions") or [])[:20]:
        if not isinstance(r, dict):
            continue
        applicant = r.get("efLimitedApplicant")
        if isinstance(applicant, list):
            applicant = "、".join(str(a) for a in applicant)
        rows.append(
            {
                "案号": str(_pick(r, "efCaseNumber", "caseNo", "案号") or "-"),
                "执行法院": str(
                    _pick(r, "efExecutiveCourt", "court", "执行法院") or "-"
                ),
                "申请执行人": str(
                    applicant or _pick(r, "applicant", "申请执行人") or "-"
                ),
                "被限制人": str(_pick(r, "efLimitedPersonName", "被限制人") or "-"),
                "发布日期": str(
                    _pick(
                        r, "efLimitedPersonCasePublishTime", "publishDate", "发布日期"
                    )
                    or "-"
                ),
            }
        )
    return rows


def _anomaly_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Business anomaly (经营异常) detail records."""
    rows = []
    for a in (_risk(data).get("anomalies") or [])[:20]:
        if not isinstance(a, dict):
            continue
        rows.append(
            {
                "列入原因": str(_pick(a, "createReason", "reason", "列入原因") or "-"),
                "决定机关": str(
                    _pick(a, "createAuthority", "department", "决定机关") or "-"
                ),
                "列入日期": str(_pick(a, "createDate", "inDate", "列入日期") or "-"),
                "移出日期": str(
                    _pick(a, "removeDate", "outDate", "移出日期") or "未移出"
                ),
                "状态": "已移出" if (_pick(a, "removeDate", "outDate")) else "在列",
            }
        )
    return rows


def _penalty_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Administrative penalty (行政处罚) detail records."""
    rows = []
    for p in (_risk(data).get("penalties") or [])[:20]:
        if not isinstance(p, dict):
            continue
        if p.get("text") and len(p) <= 2:
            continue
        rows.append(
            {
                "处罚类型": str(_pick(p, "punishType", "处罚类型") or "-"),
                "处罚内容": str(
                    _pick(p, "punishContent", "penaltyContent", "处罚内容") or "-"
                ),
                "决定机关": str(
                    _pick(p, "punishAuthority", "department", "决定机关") or "-"
                ),
                "决定日期": str(
                    _pick(p, "punishDecisionDate", "penaltyDate", "决定日期") or "-"
                ),
                "文号": str(_pick(p, "punishId", "penaltyNo", "文号") or "-"),
            }
        )
    return rows


def _mortgage_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Chattel mortgage (动产抵押) detail records."""
    rows = []
    for m in (_risk(data).get("mortgages") or [])[:20]:
        if not isinstance(m, dict):
            continue
        if m.get("text") and len(m) <= 2:
            continue
        rows.append(
            {
                "登记编号": str(_pick(m, "mortgageRegNum", "登记编号") or "-"),
                "抵押权人": str(_pick(m, "mortgagee", "抵押权人") or "-"),
                "金额": str(_pick(m, "pledgeAmount", "金额") or "-"),
                "状态": str(_pick(m, "status", "状态") or "-"),
                "登记日期": str(_pick(m, "regDate", "登记日期") or "-"),
            }
        )
    return rows


def _operation_kv(data: Mapping[str, Any]) -> Dict[str, str]:
    op = _operation(data)
    scale = op.get("scale") or {}
    out: Dict[str, str] = {}
    for label, keys in [
        ("人员规模", ("staff", "人员规模", "enterpriseScale")),
        ("年营业额", ("turnover", "年营业额", "annualTurnover")),
    ]:
        v = _pick(scale, *keys)
        if v not in (None, "", "-"):
            out[label] = str(v)
    fin_n = _i(op.get("financing_count"))
    if fin_n is not None:
        out["融资轮次"] = str(fin_n)
    rankings = op.get("rankings") or []
    if rankings:
        out["上榜记录"] = str(len(rankings))
    return out


def _literal(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        ):
            try:
                return ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                return value
    return value


def _readable_address(value: Any) -> str:
    obj = _literal(value)
    if isinstance(obj, dict):
        prefix = "".join(
            str(obj.get(k) or "") for k in ("province", "city", "district")
        )
        text = (
            str(obj.get("value") or "")
            .strip()
            .replace("中国.", "")
            .replace("中国", "")
            .replace(".", "")
        )
        if prefix:
            index = text.rfind(prefix)
            if index >= 0:
                base = text[index:]
                suffix = base[len(prefix) :]
                city_district = "".join(
                    str(obj.get(k) or "") for k in ("city", "district")
                )
                while city_district and suffix.startswith(city_district):
                    suffix = suffix[len(city_district) :]
                return prefix + suffix
            return prefix
        if text:
            return text
    return str(value) if value not in (None, "", "-") else "-"


def _readable_list(value: Any) -> str:
    obj = _literal(value)
    if isinstance(obj, (list, tuple, set)):
        return "；".join(str(x) for x in obj if x not in (None, "", "-"))
    return str(value) if value not in (None, "", "-") else "-"


def _channel_kv(data: Mapping[str, Any]) -> Dict[str, str]:
    channel = _channel(data)
    out: Dict[str, str] = {}
    search_total = _i(channel.get("search_total"))
    if search_total is not None:
        out["渠道关联搜索返回数"] = str(search_total)
    financial = channel.get("financialStat") or {}
    sales = channel.get("salesStat") or {}
    if isinstance(financial, dict) and financial.get("categoryCount") is not None:
        out["财务维度同行总数"] = str(financial.get("categoryCount"))
    if isinstance(sales, dict) and sales.get("categoryCount") is not None:
        out["销售维度同行总数"] = str(sales.get("categoryCount"))
    out["关系核验状态"] = "关联搜索结果未逐条确认与目标法人的关系" if out else "-"
    return out


def _factory_kv(data: Mapping[str, Any]) -> Dict[str, str]:
    factory = _factory(data)
    out: Dict[str, str] = {}
    if factory.get("factoryName"):
        out["工厂记录名称"] = str(factory["factoryName"])
    if factory.get("factoryNameId"):
        out["工厂记录主体ID"] = str(factory["factoryNameId"])
    if factory.get("factoryAddress"):
        out["工厂地址"] = _readable_address(factory["factoryAddress"])
    capacity_known = any(
        _pick(factory, key) not in (None, "", "-")
        for key in (
            "assemblyLine",
            "boarderStaffNumber",
            "inspectionStaffNumber",
            "monthlyProductionAmountValue",
            "monthlyProductionAmountValue_caps",
        )
    ) or bool(factory.get("mainDeviceList"))
    if capacity_known and factory.get("factoryScale"):
        out["工厂规模标签"] = str(factory["factoryScale"])
    product_count = _i(factory.get("mainProductCount"))
    if product_count is not None:
        out["主要产品统计数"] = str(product_count)
    if not out and not capacity_known:
        return {}
    out["产能证据状态"] = (
        "核心产能字段已返回"
        if capacity_known
        else "产线/人员/设备/月产能未返回，不评价产能"
    )
    out["主体关系状态"] = "需以统一社会信用代码或主体ID人工核验工厂记录归属"
    return out


def _recruitment_kv(data: Mapping[str, Any]) -> Dict[str, str]:
    rec = _recruitment(data)
    out: Dict[str, str] = {}
    for label, key in [("当前在招", "current"), ("近三月招聘", "last_3m")]:
        v = _i(rec.get(key))
        if v is not None:
            out[label] = str(v)
    current = _i(rec.get("current"))
    last3 = _i(rec.get("last_3m"))
    if current is not None and last3 is not None and current == last3:
        out["窗口口径"] = (
            "上游当前值与近三月值相同，两个时间窗口不可区分；"
            "不能视为两次独立招聘信号"
        )
    sal = rec.get("avg_salary")
    if sal not in (None, "", "-"):
        try:
            out["平均薪酬"] = f"{float(str(sal).replace(',', '')):.2f} 元/月"
        except (TypeError, ValueError):
            out["平均薪酬"] = str(sal)
    welfare = rec.get("welfare") or []
    if welfare:
        out["福利标签"] = "、".join(str(x) for x in welfare if x)
    return out


# --------------------------------------------------------------------------- #
# Payload assembly
# --------------------------------------------------------------------------- #
def _quality_nonempty(value: Any) -> bool:
    """0/False are real values; only None/''/[]/{} count as empty."""
    if value is None or value == "":
        return False
    if isinstance(value, dict):
        return any(_quality_nonempty(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_quality_nonempty(v) for v in value)
    return True


def _refresh_quality_report(report: Dict[str, Any]) -> None:
    data_source = report.get("data_source")
    core = report.get("core_analysis")
    if not isinstance(data_source, dict) or not isinstance(core, dict):
        return
    sections = core.get("sections")
    if not isinstance(sections, list):
        return
    declared = [s for s in sections if isinstance(s, dict)]
    populated = sum(
        1 for section in declared if _quality_nonempty(core.get(section.get("key")))
    )
    quality = data_source.get("quality_report")
    if not isinstance(quality, dict):
        quality = {}
    # The composer declares every section it attempted before empty bodies are
    # dropped. Keep that declared total so a review pass cannot turn missing
    # dimensions into a false 100% coverage; grow it only when a section was
    # added, and fall back to the current count for foreign payloads.
    try:
        previous_total = int(quality.get("total_sections") or 0)
    except (TypeError, ValueError):
        previous_total = 0
    total = max(len(declared), populated, previous_total)
    quality["total_sections"] = total
    quality["populated_sections"] = populated
    quality["empty_sections"] = max(0, total - populated)
    quality["coverage_pct"] = round(populated / total * 100) if total else 0
    data_source["quality_report"] = quality


def apply_content_review(
    report: Mapping[str, Any], calls: Any = None
) -> Dict[str, Any]:
    """Offline content repair for a frozen supplier-evaluation report."""
    reviewed = json.loads(json.dumps(report, ensure_ascii=False))
    old_conflict = "上游原等级与司法记录冲突待核验"
    new_conflict = "上游风险等级未在报告中保留；司法暴露需人工核验"
    for key in ("abstract", "summary"):
        if old_conflict in str(reviewed.get(key) or ""):
            reviewed[key] = str(reviewed[key]).replace(old_conflict, new_conflict)
    verdict = reviewed.get("verdict")
    if isinstance(verdict, dict):
        for key in ("summary", "level"):
            if old_conflict in str(verdict.get(key) or ""):
                verdict[key] = str(verdict[key]).replace(old_conflict, new_conflict)
    for metric in reviewed.get("metrics") or []:
        if metric.get("label") == "上游风险评分":
            metric["hint"] = (
                "上游原始评分；接口未返回阈值/方向说明，"
                "存在司法暴露时不得解读为低风险"
            )
        if metric.get("label") == "数据产品账期标签" and "上游原始标签" not in str(
            metric.get("value") or ""
        ):
            metric["value"] = f"{metric.get('value')}（上游原始标签）"
            metric["hint"] = "上游数据产品原始标签；不代表财务稳健或账期可控"
    for record in reviewed.get("representative_records") or []:
        if old_conflict in str(record.get("关键记录") or ""):
            record["关键记录"] = str(record["关键记录"]).replace(
                old_conflict, new_conflict
            )
    core = reviewed.get("core_analysis")
    if isinstance(core, dict):
        profile = core.get("se_profile")
        if isinstance(profile, dict) and profile.get("工厂地址"):
            profile["工厂地址"] = _readable_address(profile["工厂地址"])
        clues = core.get("se_factory_platform_clues")
        if isinstance(clues, dict) and clues.get("管理体系认证"):
            clues["管理体系认证"] = _readable_list(clues["管理体系认证"])
        channel = core.get("se_channel")
        if isinstance(channel, dict):
            relabeled = {}
            for key, value in channel.items():
                if key == "财务分类样本数":
                    relabeled["财务维度同行总数"] = value
                elif key == "销售分类样本数":
                    relabeled["销售维度同行总数"] = value
                else:
                    relabeled[key] = value
            core["se_channel"] = relabeled
        rec = core.get("se_recruitment")
        if isinstance(rec, dict):
            current = _i(rec.get("当前在招"))
            last3 = _i(rec.get("近三月招聘"))
            if current is not None and last3 is not None and current == last3:
                rec["窗口口径"] = (
                    "上游当前值与近三月值相同，两个时间窗口不可区分；"
                    "不能视为两次独立招聘信号"
                )
            salary = rec.get("平均薪酬")
            try:
                rec["平均薪酬"] = f"{float(str(salary).replace(',', '')):.2f} 元/月"
            except (TypeError, ValueError):
                pass
        for section in core.get("sections") or []:
            if section.get("key") == "se_holders":
                note = str(section.get("note") or "")
                extra = "上市/股份公司可能按股份类别返回，不等同自然人股东名单"
                if extra not in note:
                    section["note"] = (note + "；" if note else "") + extra
    for insight in reviewed.get("insights") or []:
        evidence = str(insight.get("evidence") or "")
        evidence = evidence.replace("财务分类样本", "财务维度同行总数").replace(
            "销售分类样本", "销售维度同行总数"
        )
        insight["evidence"] = evidence
    caliber = reviewed.get("caliber")
    if isinstance(caliber, dict):
        note = "字段已整理为可读文本；同行总数按上游 categoryCount 口径标注，未新增推断。"
        if note not in str(caliber.get("limit") or ""):
            caliber["limit"] = str(caliber.get("limit") or "") + note
    _refresh_quality_report(reviewed)
    return reviewed


def build_direct_payload(
    enterprise: str, keyword_type: str, *, dry_run: bool, skills_root: str,
    max_pages: Optional[int] = None, calls: Any = None,
) -> Dict[str, Any]:
    # 1. Collect multi-source data (live MCP or cached reports)
    data = orch.collect_direct(
        enterprise, keyword_type, dry_run=dry_run, skills_root=skills_root,
        detail_max_pages=max_pages,
    )
    meta = data.get("_meta") or {}
    evidence = calls
    if evidence is None:
        evidence = data.get("calls")
    if evidence is None:
        evidence = meta.get("calls")
    resolved = meta.get("resolved") or {}
    canon = resolved.get("enterprise") or enterprise
    errors = meta.get("errors") or {}
    source_mode = "live_mcp" if meta.get("source") == "live" else "cached_reports"
    identity_base = _base(data)
    identity_name = str(_pick(identity_base, "企业名称", "name", "名称") or "").strip()
    identity_code = str(
        _pick(identity_base, "统一社会信用代码", "socialCreditCode", "信用代码") or ""
    ).strip()
    subject_confirmed = (
        identity_name not in ("", "-")
        and identity_code not in ("", "-")
        and identity_name == canon
    )
    subject_reason = (
        "工商基础信息中的企业名称和统一社会信用代码已返回"
        if subject_confirmed
        else "工商基础信息未返回可核验企业名称及统一社会信用代码"
    )

    if errors:
        for k, msg in list(errors.items())[:5]:
            print(f"⚠️  工具调用失败 [{k}]: {msg[:120]}", file=sys.stderr)

    # 2. Cross-domain analysis
    cross = xa.analyze(data)
    verdict = dict(cross["verdict"])
    scores: Dict[str, Any] = {"items": [], "average": None}
    factual_metric_labels = {
        "上游风险评分",
        "对外投资",
        "行政处罚",
        "注册资本",
        "资本实缴率",
        "融资轮次",
        "产线数",
        "普工人数",
        "数据产品账期标签",
        "在招岗位",
        "限制高消费",
        "开庭公告",
        "经营异常",
        "股东数量",
        "成立年限",
    }
    cross["metrics"] = [
        dict(item)
        for item in cross["metrics"]
        if item.get("label") in factual_metric_labels
    ]
    cross["section_specs"] = [
        spec for spec in cross["section_specs"] if spec.get("key") != "se_specialty"
    ]
    cross["section_data"].pop("se_specialty", None)
    cross["insights"] = [
        item
        for item in cross["insights"]
        if "评分" not in str(item) and "观察值" not in str(item)
    ]
    verdict["specialty_average"] = None
    judicial_exposure = bool(
        (_i(_risk(data).get("court_hearings_total")) or 0)
        or (_i(_risk(data).get("restrictions_total")) or 0)
    )
    upstream_level = str(_risk(data).get("level") or "").strip()
    if upstream_level:
        risk_level_display = (
            f"{upstream_level}（存在司法暴露，需人工核验；不作低风险背书）"
            if judicial_exposure and not any(
                token in upstream_level for token in ("高", "严重")
            )
            else upstream_level
        )
    else:
        risk_level_display = (
            "上游未返回风险等级（司法暴露需人工核验）"
            if judicial_exposure
            else "上游未返回风险等级"
        )
    verdict["key_concerns"] = [
        concern
        for concern in verdict.get("key_concerns", [])
        if concern != "供货能力偏弱"
    ]
    if not subject_confirmed:
        verdict.update(
            level="主体未确认",
            recommendation="仅作具名检索线索",
            summary="工商名称与统一社会信用代码未同时确认；返回内容不得归属于目标主体，不作供应商准入评级。",
            blockers=[],
            key_concerns=["主体身份未确认"],
        )
    elif verdict.get("blockers"):
        verdict.update(
            level="不予综合评级",
            recommendation="人工司法核验",
            summary=f"发现需人工核验的司法或合规线索：{'、'.join(verdict['blockers'])}；不生成自定义综合或专项评分。",
        )
    else:
        verdict.update(
            level="事实观察（不评分）",
            recommendation="逐项人工核验",
            summary="报告仅整理公开事实和上游原始口径；缺少经验证模型、审计财务与同行分母，不生成自定义综合或专项评分。",
        )
    risk_errors = any(str(key).startswith("risk_") for key in errors)
    evidence_gate = (
        subject_confirmed and xa._risk_evidence_known(data) and not risk_errors
    )
    if not evidence_gate:
        cross["insights"] = (
            []
            if not subject_confirmed
            else [
                item
                for item in cross["insights"]
                if not any(
                    word in str(item.get("feature") or "")
                    for word in ("风险", "司法", "诉讼")
                )
            ]
        )

    # 3. Build core_analysis sections + data
    sections: List[Dict[str, Any]] = []
    core: Dict[str, Any] = {}
    attempted_sections = 0

    def _effective(value: Any) -> bool:
        if value in (None, "", "-", [], {}):
            return False
        if isinstance(value, dict):
            return any(_effective(v) for v in value.values())
        if isinstance(value, list):
            return any(_effective(v) for v in value)
        return True

    def _add(spec: Dict[str, Any], body: Any) -> None:
        nonlocal attempted_sections
        attempted_sections += 1
        key = spec["key"]
        # radar carries its data in the chart spec (indicators/series), not the body
        if spec.get("kind") == "radar":
            sections.append(spec)
            if body:
                core[key] = body
            return
        if _effective(body):
            sections.append(spec)
            core[key] = body

    # 供应商概况（factory profile + base）
    factory_kv = _factory_kv(data)
    base_kv = _base_kv(data)
    profile_kv = {**factory_kv, **base_kv}
    if profile_kv:
        _add(
            {
                "key": "se_profile",
                "title": "供应商概况",
                "kind": "kv",
                "note": "工厂概况 + 工商基础信息",
            },
            profile_kv,
        )

    # 工厂平台字段仅作线索，不能替代经核验的供货能力。
    factory_clues = {
        "产线数": _pick(_factory(data), "assemblyLine"),
        "普工人数": _pick(_factory(data), "boarderStaffNumber"),
        "质检人数": _pick(_factory(data), "inspectionStaffNumber"),
        "主要设备": "、".join(
            str(d)
            for d in (_factory(data).get("mainDeviceList") or [])
            if _effective(d)
        ),
        "管理体系认证": _readable_list(
            _pick(_factory(data), "managementSystemCertification")
        )
        if _pick(_factory(data), "managementSystemCertification")
        else None,
        "月产能": _pick(_factory(data), "monthlyProductionAmountValue_caps"),
        "服务品牌数": _i(_factory(data).get("serviceBrandCount")),
        "主要产品数": _i(_factory(data).get("mainProductCount")),
    }
    capabilities_kv = {
        label: str(value) for label, value in factory_clues.items() if _effective(value)
    }
    _add(
        {
            "key": "se_factory_platform_clues",
            "title": "工厂平台返回线索",
            "kind": "kv",
            "note": "仅列工厂平台实际返回字段；字段归属及产能口径需人工核验，不据此宣称供货能力或产能匹配",
        },
        capabilities_kv,
    )

    # 渠道分析
    channel_kv = _channel_kv(data)
    _add(
        {
            "key": "se_channel",
            "title": "渠道关联搜索事实",
            "kind": "kv",
            "note": "渠道关联搜索/分类统计；与目标法人的关系未逐条确认，不作领先或覆盖能力结论",
        },
        channel_kv,
    )

    # cross-analysis sections (shareholders, investments, specialty matrix)
    for spec in cross["section_specs"]:
        _add(spec, cross["section_data"].get(spec["key"]))

    # risk gauge + risk dimension counts — paired to avoid whitespace
    risk_score = _i(_risk(data).get("score"))
    if risk_score is not None:
        _add(
            {
                "key": "se_risk_gauge",
                "title": "综合风险评分",
                "kind": "gauge",
                "chart": {"value_key": "风险评分", "level_key": "风险等级", "max": 100},
                "note": "上游风险评分原始口径；若与司法事件数量冲突，不作为低风险背书",
                "pair_with": "se_risk_dims",
            },
            {"风险评分": risk_score, "风险等级": risk_level_display},
        )
    risk_rows = _risk_dim_rows(data)
    _add(
        {
            "key": "se_risk_dims",
            "title": "风险维度统计",
            "kind": "table",
            "note": "各风险维度记录数（供应商合规核查）",
            "columns": [("风险维度", "风险维度"), ("记录数", "记录数")],
        },
        risk_rows,
    )

    # --- 风险案件明细（供应商评估核心：展开具体案件，而非只给数字）---
    hearing_rows = _hearing_rows(data)
    _add(
        {
            "key": "se_hearings",
            "title": "开庭公告明细",
            "kind": "table",
            "note": f"报告总量 {_risk(data).get('court_hearings_total') if _risk(data).get('court_hearings_total') is not None else '未知'} 条（当前展示 {len(hearing_rows)} 条）；保留上游案号/日期/主体用于人工去重，缺少案号或日期的记录无法逐案去重",
            "columns": [
                ("案号", "案号"),
                ("案由", "案由"),
                ("法院", "法院"),
                ("相关主体", "相关主体"),
                ("开庭/发布日期", "开庭/发布日期"),
                ("公告类型", "公告类型"),
                ("去重键状态", "去重键状态"),
            ],
        },
        hearing_rows,
    )

    restriction_rows = _restriction_rows(data)
    _add(
        {
            "key": "se_restrictions",
            "title": "限制高消费明细",
            "kind": "table",
            "note": "限制高消费是供应商评估重大风险信号，需核查执行标的与履行情况",
            "columns": [
                ("案号", "案号"),
                ("执行法院", "执行法院"),
                ("申请执行人", "申请执行人"),
                ("被限制人", "被限制人"),
                ("发布日期", "发布日期"),
            ],
        },
        restriction_rows,
    )

    anomaly_rows = _anomaly_rows(data)
    _add(
        {
            "key": "se_anomalies",
            "title": "经营异常明细",
            "kind": "table",
            "note": "经营异常名录记录（如通过住所无法联系），核查是否已移出",
            "columns": [
                ("列入原因", "列入原因"),
                ("决定机关", "决定机关"),
                ("列入日期", "列入日期"),
                ("移出日期", "移出日期"),
                ("状态", "状态"),
            ],
        },
        anomaly_rows,
    )

    penalty_rows = _penalty_rows(data)
    _add(
        {
            "key": "se_penalties",
            "title": "行政处罚明细",
            "kind": "table",
            "note": "行政处罚记录，核查违法事实与处罚影响",
            "columns": [
                ("处罚类型", "处罚类型"),
                ("处罚内容", "处罚内容"),
                ("决定机关", "决定机关"),
                ("决定日期", "决定日期"),
                ("文号", "文号"),
            ],
        },
        penalty_rows,
    )

    mortgage_rows = _mortgage_rows(data)
    _add(
        {
            "key": "se_mortgages",
            "title": "动产抵押明细",
            "kind": "table",
            "note": "动产抵押反映资产质押状况",
            "columns": [
                ("登记编号", "登记编号"),
                ("抵押权人", "抵押权人"),
                ("金额", "金额"),
                ("状态", "状态"),
                ("登记日期", "登记日期"),
            ],
        },
        mortgage_rows,
    )

    # operation
    op_kv = _operation_kv(data)
    _add(
        {
            "key": "se_operation",
            "title": "经营规模与资本运作",
            "kind": "kv",
            "note": "人员规模 / 营业额 / 融资 / 上榜记录",
        },
        op_kv,
    )

    # recruitment
    rec_kv = _recruitment_kv(data)
    _add(
        {
            "key": "se_recruitment",
            "title": "招聘公开统计",
            "kind": "kv",
            "note": "招聘平台公开字段事实统计；“当前/近三月”为上游窗口标签，未返回精确观察起止日期，不能单独证明经营动能、产能或履约能力",
        },
        rec_kv,
    )

    # 4. Metrics (凑 4 的倍数)
    metrics: List[Dict[str, Any]] = list(cross["metrics"])
    for item in metrics:
        if item.get("label") == "上游风险评分":
            item["hint"] = "上游原始口径；若与司法事件数量冲突，不作为低风险背书"
            if judicial_exposure:
                item.pop("delta", None)
        elif item.get("label") in ("产线数", "普工人数"):
            item["hint"] = "工厂平台实际返回字段；归属及口径待核验"
        elif item.get("label") == "数据产品账期标签":
            item["hint"] = "上游数据产品原始标签；不代表财务稳健或账期可控"
        elif item.get("label") == "在招岗位":
            item["hint"] = "招聘平台公开数量；不代表产能或履约能力"

    # 5. Insights (cross-domain first, then can supplement)
    insights: List[Dict[str, Any]] = list(cross["insights"])

    # 6. Representative records (key cross-domain facts for the "Records" section)
    rep_records: List[Dict[str, str]] = []
    invests = _investments(data)
    inv_total = _risk(data).get("investments_total") or len(invests)
    cancelled = [
        i
        for i in invests
        if "注销" in str(_pick(i, "operStatus", "经营状态", "状态") or "")
    ]
    if inv_total:
        rep_records.append(
            {
                "维度": "对外投资",
                "关键记录": f"{inv_total} 家关联企业"
                + (f"（其中 {len(cancelled)} 家已注销）" if cancelled else ""),
            }
        )
    ls = xa._litigation_summary(data)
    if ls["executed"]:
        rep_records.append(
            {"维度": "执行风险", "关键记录": f"被执行记录 {ls['executed']} 条"}
        )
    risk_score = _i(_risk(data).get("score"))
    if risk_score is not None:
        rep_records.append(
            {
                "维度": "风险评级",
                "关键记录": f"上游风险评分 {risk_score}（{risk_level_display}）",
            }
        )
    channel_count = _i(_channel(data).get("channelCount"))
    if channel_count:
        rep_records.append(
            {"维度": "渠道覆盖", "关键记录": f"渠道总数 {channel_count}"}
        )
    assembly_line = _i(_factory(data).get("assemblyLine"))
    if assembly_line:
        rep_records.append({"维度": "产能规模", "关键记录": f"产线数 {assembly_line}"})
    hearing_total = _risk(data).get("court_hearings_total")
    if hearing_total:
        rep_records.append(
            {"维度": "诉讼记录", "关键记录": f"开庭公告 {hearing_total} 条"}
        )
    if not rep_records:
        rep_records.append({"维度": "数据状态", "关键记录": "多维数据覆盖，详见各章节"})

    # 7. Abstract & summary
    n_sources = sum(
        1
        for d in (
            data.get("enterprise"),
            data.get("risk"),
            data.get("operation"),
            data.get("channel"),
            data.get("factory"),
            data.get("recruitment"),
        )
        if _effective(d)
    )
    abstract_parts = [
        f"本报告以「{canon}」为评估对象，直接聚合工商、风险、经营、渠道、工厂、招聘 {n_sources} 大数据源的多维原始数据，",
    ]
    if verdict["blockers"]:
        abstract_parts.append(
            f"发现 {len(verdict['blockers'])} 项重大风险阻断项：{'、'.join(verdict['blockers'])}。"
        )
    if verdict["key_concerns"]:
        abstract_parts.append(f"需关注：{'、'.join(verdict['key_concerns'][:3])}。")
    abstract_parts.append(verdict["summary"])
    abstract = "".join(abstract_parts)

    if not subject_confirmed:
        sections = []
        core = {}
        metrics = []
        insights = []
        rep_records = [
            {
                "维度": "检索状态",
                "关键记录": "仅形成具名检索线索；工商名称与统一社会信用代码未同时确认，所有返回记录归属待核验",
            }
        ]
        abstract = (
            f"本报告仅记录对关键词「{enterprise}」的具名检索线索。"
            "工商名称与统一社会信用代码未同时确认，返回的风险、投资、经营、渠道、工厂及招聘记录不得归属于目标主体；不作供应商准入评级。"
        )

    # Upstream risk scores may remain as explicitly sourced factual metrics,
    # but must never be promoted into this report's own gauge or "综合" chart.
    gauge_keys = {
        str(section.get("key") or "")
        for section in sections
        if section.get("kind") == "gauge"
    }
    if gauge_keys:
        sections = [section for section in sections if section.get("kind") != "gauge"]
        for key in gauge_keys:
            core.pop(key, None)
        attempted_sections = max(0, attempted_sections - len(gauge_keys))

    # quality report
    populated = sum(
        1
        for s in sections
        if s.get("kind") == "radar" or _effective(core.get(s["key"]))
    )
    quality = {
        "total_sections": attempted_sections,
        "populated_sections": populated,
        "empty_sections": attempted_sections - populated,
        "coverage_pct": round(populated / max(1, attempted_sections) * 100),
        "data_sources": n_sources,
        "cross_insights": len(insights),
    }

    report = {
        "report_type": REPORT_TYPE,
        "title": f"{canon} 供应商评估报告",
        "banner": BANNER,
        "subject": {
            "enterprise": canon,
            "match_raw": enterprise,
            "resolved": subject_confirmed,
            "resolve_reason": subject_reason,
        },
        "abstract": abstract,
        "summary": abstract,
        "executive_summary": [verdict["summary"]]
        + [i["interpretation"] for i in insights[:4]],
        "verdict": verdict,
        "specialty_scores": scores,
        "metrics": metrics,
        "caliber": {
            "match_target": canon,
            "match_type": "供应商评估（直接聚合 6 个 MCP：工商/风险/经营/渠道/工厂/招聘）",
            "data_scope": f"覆盖 {n_sources}/6 大数据源，{len(sections)} 个明细章节，{len(insights)} 条跨维度洞察",
            "products": [
                "企业大数据",
                "企业风险洞察",
                "企业经营分析",
                "渠道洞察",
                "工厂洞察",
                "招聘大数据",
            ],
            "limit": "未确认主体时所有返回仅为具名检索线索；已确认主体时也仅整理公开事实，不生成自定义评分；工厂平台字段、渠道关系及目标行业适用性需逐条核验，并结合实地考察与财务审计决策。",
        },
        "core_analysis": {**core, "sections": sections},
        "representative_records": rep_records,
        "insights": insights,
        "data_source": {
            "mcp_server": "6 MCP（工商/风险/经营/渠道/工厂/招聘）",
            "mcp_servers": [
                "enterprise-mcp-server",
                "enterprise-risk-mcp-server",
                "enterprise-operation-mcp-server",
                "factory-channel-mcp-server",
                "factory-insight-mcp-server",
                "recruitment-mcp-server",
            ],
            "mode": source_mode,
            "dry_run": dry_run,
            "generated_at": dt.datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "quality_report": quality,
            "tool_errors": list(errors.keys()) if errors else [],
        },
    }
    if meta.get("source") == "live":
        from common import attach_pagination

        report = attach_pagination(report, meta.get("pagination_payloads") or {})
        call_usage = meta.get("call_usage")
        if isinstance(call_usage, dict) and call_usage:
            report["data_source"]["call_usage"] = call_usage
        if max_pages is None:
            budget_note = (
                "明细接口默认按单页预算采集（每接口仅请求第 1 页，该页同时用于分析与上游 total 发现，不重复计费）；"
                "如需更多明细页，请先规划所需结论与数据维度，再用 --max-pages N 明确页数预算；"
                "若预算不足以支撑关键结论，必须说明证据缺口与预计所需额外页数，不得悄悄降级结论或扩大计费范围。"
            )
            report["abstract"] += budget_note
            report["summary"] += budget_note
            report["caliber"]["limit"] += budget_note
        for note in (meta.get("schema_limited") or {}).values():
            report["abstract"] += note
            report["summary"] += note
            report["caliber"]["limit"] += note
    return apply_content_review(report, evidence)
