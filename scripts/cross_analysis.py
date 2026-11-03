#!/usr/bin/env python3
"""Cross-domain analysis engine for supplier-evaluation reports.

Consumes the unified NormalizedData from mcp_orchestration and produces
cross-dimensional insights that NO single atomic skill can generate on its own:

  1. 供货能力       — 工厂产能/设备/产线 + 渠道覆盖
  2. 合规健康度     — 处罚/异常/限高/违法 倒扣
  3. 财务稳健性     — 注册资本/实缴/融资/规模
  4. 风险隔离度     — 投资广度 × 风险评分 + 被执行
  5. 供应商准入结论   — 综合判定 + 关键关注点

All evidence is grounded in actual data; missing dimensions are skipped (never
fabricated).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional


# --------------------------------------------------------------------------- #
# Tolerant field extraction (handles both live MCP and cached report shapes)
# --------------------------------------------------------------------------- #
def source_ratio_percent(value: Any) -> Optional[Decimal]:
    """Return a percentage as Decimal without rounding; None when unavailable.

    Accepts a 0-1 fraction, an already-percent number, a '12.3456%' string,
    or a dict. Zero is a real value; only missing/invalid input returns None.
    """
    if isinstance(value, dict):
        value = value.get("value", value.get("ratio", value.get("percent")))
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text or text in {"-", "—"}:
        return None
    if "%" in text:
        text = text.replace("%", "").strip()
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if number != 0 and abs(number) <= 1:
        number *= 100
    return number


def format_source_ratio(value: Any) -> str:
    """Render an upstream ratio without rounding, zero-padding, or unit guessing.

    A percent string such as '12.3400%' is returned verbatim. Numeric 0-1
    fractions keep their original significant digits (0.123456 -> 12.3456%).
    Zero renders as '0%'; missing or invalid values render as '-'.
    """
    if isinstance(value, dict):
        value = value.get("value", value.get("ratio", value.get("percent")))
    if value is None:
        return "-"
    text = str(value).strip()
    if not text or text in {"-", "—"}:
        return "-"
    if "%" in text:
        return text
    number = source_ratio_percent(value)
    if number is None:
        return text
    return f"{format(number.normalize(), 'f')}%"


def _pick(d: Any, *keys: str) -> Any:
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if v not in (None, "", "-", []):
            return v
    return None


def _f(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(
            str(value)
            .replace(",", "")
            .replace("万", "")
            .replace("%", "")
            .replace("亿", "")
        )
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> Optional[int]:
    f = _f(value)
    return int(f) if f is not None else None


def _ratio_pct(value: Any) -> Optional[float]:
    """Parse '67%' / '0.67' / 67 into a 0-100 percentage."""
    if value is None:
        return None
    s = str(value).strip()
    if "%" in s:
        try:
            return float(s.replace("%", "").strip())
        except ValueError:
            return None
    f = _f(value)
    if f is None:
        return None
    return f * 100 if f <= 1 else f


# --------------------------------------------------------------------------- #
# Data accessors
# --------------------------------------------------------------------------- #
def _holders(data: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return list(data.get("enterprise", {}).get("holders") or [])


def _investments(data: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return list(data.get("enterprise", {}).get("investments") or [])


def _base(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("enterprise", {}).get("base") or {})


def _risk(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("risk") or {})


def _litigation(data: Mapping[str, Any]) -> Dict[str, Any]:
    lit = _risk(data).get("litigation") or {}
    return lit if isinstance(lit, dict) else {}


def _litigation_summary(data: Mapping[str, Any]) -> Dict[str, Any]:
    risk = _risk(data)
    lit = _litigation(data)
    hearings = _i(risk.get("court_hearings_total"))
    executed = _i(risk.get("restrictions_total"))
    case_count = _i(lit.get("case_count") or lit.get("caseCount"))
    defendant = _i(lit.get("as_defendant") or lit.get("asDefendant"))
    plaintiff = _i(lit.get("as_plaintiff") or lit.get("asPlaintiff"))
    announcements = _i(lit.get("法院公告数"))
    judgments = _i(lit.get("裁判文书数"))
    dishonest = _i(lit.get("失信被执行人数"))
    known = any(
        v is not None and v > 0
        for v in (
            hearings,
            executed,
            case_count,
            defendant,
            plaintiff,
            announcements,
            judgments,
            dishonest,
        )
    ) or bool(risk.get("level"))
    if not known:
        return {
            "case_count": None,
            "as_defendant": None,
            "as_plaintiff": None,
            "hearings": None,
            "announcements": None,
            "judgments": None,
            "executed": None,
            "dishonest": None,
            "has_role_detail": False,
        }
    if case_count is None:
        case_count = hearings
    return {
        "case_count": case_count,
        "as_defendant": defendant,
        "as_plaintiff": plaintiff,
        "hearings": hearings,
        "announcements": announcements,
        "judgments": judgments,
        "executed": executed,
        "dishonest": dishonest,
        "has_role_detail": defendant is not None or plaintiff is not None,
    }


def _operation(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("operation") or {})


def _channel(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("channel") or {})


def _factory(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("factory") or {})


def _recruitment(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("recruitment") or {})


def _risk_evidence_known(data: Mapping[str, Any]) -> bool:
    """Distinguish an explicitly queried risk result from an empty/failed domain."""
    risk = _risk(data)
    marker = risk.get("_evidence_known")
    if marker is not None:
        return marker is True
    if risk.get("score") is not None or risk.get("level") not in (None, "", "-"):
        return True
    return any(
        risk.get(key) is not None
        for key in (
            "court_hearings_total",
            "restrictions_total",
            "penalties_total",
            "anomalies_total",
        )
    )


# --------------------------------------------------------------------------- #
# Specialty scores (each 0-100, or None if data unavailable)
# --------------------------------------------------------------------------- #
def score_supply_capability(data: Mapping[str, Any]) -> Optional[float]:
    factory = _factory(data)
    assembly = _i(factory.get("assemblyLine"))
    production = _f(
        factory.get("monthlyProductionAmountValue")
        or factory.get("monthlyProductionAmountValue_caps")
    )
    staff = _i(factory.get("boarderStaffNumber"))
    devices = len(factory.get("mainDeviceList") or [])
    if all(v in (None, 0) for v in (assembly, production, staff, devices)):
        return None
    # Observation index only when core capacity fields exist; channel data never substitutes capacity.
    s = (
        min(30, (assembly or 0) * 5)
        + min(30, (staff or 0) / 10)
        + min(20, devices * 4)
        + (20 if production is not None else 0)
    )
    return round(min(100, s), 1)


def score_compliance_health(data: Mapping[str, Any]) -> Optional[float]:
    if not _risk_evidence_known(data):
        return None
    risk = _risk(data)
    hearings = _i(risk.get("court_hearings_total"))
    restrictions = _i(risk.get("restrictions_total"))
    penalties = _i(risk.get("penalties_total"))
    anomalies = _i(risk.get("anomalies_total"))
    if all(v is None for v in (hearings, restrictions, penalties, anomalies)):
        return None
    exposure = (
        min(60, (hearings or 0) / 5)
        + min(50, (restrictions or 0) * 10)
        + min(30, (penalties or 0) * 10)
        + min(20, (anomalies or 0) * 5)
    )
    return round(max(0, 100 - exposure), 1)


def score_financial_stability(data: Mapping[str, Any]) -> Optional[float]:
    # Registration capital, financing rounds and vendor labels are public clues,
    # not audited cash-flow, solvency or receivables evidence.
    return None


def score_risk_isolation(data: Mapping[str, Any]) -> Optional[float]:
    if not _risk_evidence_known(data):
        return None
    risk = _risk(data)
    inv = _i(risk.get("investments_total"))
    hearings = _i(risk.get("court_hearings_total"))
    restrictions = _i(risk.get("restrictions_total"))
    if all(v is None for v in (inv, hearings, restrictions)):
        return None
    exposure = (
        min(35, (inv or 0) / 5)
        + min(45, (hearings or 0) / 10)
        + min(60, (restrictions or 0) * 12)
    )
    return round(max(0, 100 - exposure), 1)


def specialty_scores(data: Mapping[str, Any]) -> Dict[str, Any]:
    items = [
        ("supply_capability", "产能证据观察", score_supply_capability(data)),
        ("compliance_health", "司法与合规健康度", score_compliance_health(data)),
        ("financial_stability", "审计财务稳健性", score_financial_stability(data)),
        ("risk_isolation", "风险隔离度", score_risk_isolation(data)),
    ]
    valid = [(key, label, value) for key, label, value in items if value is not None]
    meta = data.get("_meta") or {}
    resolved_meta = meta.get("resolved") or {}
    canon = str(resolved_meta.get("enterprise") or "").strip()
    base = _base(data)
    base_name = str(_pick(base, "企业名称", "name", "名称") or "").strip()
    code = str(
        _pick(base, "统一社会信用代码", "socialCreditCode", "信用代码") or ""
    ).strip()
    subject_ok = (
        base_name not in ("", "-")
        and code not in ("", "-")
        and (not canon or base_name == canon)
    )
    risk = _risk(data)
    hearings = _i(risk.get("court_hearings_total"))
    restrictions = _i(risk.get("restrictions_total"))
    level = str(risk.get("level") or "")
    risk_known = (hearings is not None or restrictions is not None) and bool(
        level or (hearings or 0) > 0 or (restrictions or 0) > 0
    )
    judicial_clear = (
        hearings is not None and hearings < 100 and (restrictions or 0) == 0
    )
    supply_ok = score_supply_capability(data) is not None
    eligible = (
        subject_ok
        and not meta.get("errors")
        and risk_known
        and judicial_clear
        and supply_ok
        and len(valid) >= 3
    )
    avg = (
        round(sum(value for _, _, value in valid) / len(valid), 1) if eligible else None
    )
    return {
        "items": items,
        "valid": valid,
        "average": avg,
        "rating_eligible": eligible,
        "minimum_domains": 3,
        "gate_reason": None if eligible else "主体、关键域或司法风险门禁未满足",
    }


def insight_supply_risk(data: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    supply = score_supply_capability(data)
    risk_known = _risk_evidence_known(data)
    hearings = _i(_risk(data).get("court_hearings_total")) if risk_known else None
    restrictions = _i(_risk(data).get("restrictions_total")) if risk_known else None
    if supply is None and hearings is None and restrictions is None:
        return None
    parts = [f"产能观察指数 {supply}" if supply is not None else "核心产能字段未知"]
    if hearings is not None:
        parts.append(f"开庭 {hearings} 条")
    if restrictions is not None:
        parts.append(f"限高 {restrictions} 条")
    interp = (
        "司法暴露触发人工核验门禁，不予供应商综合评级。"
        if (hearings or 0) >= 100 or (restrictions or 0) > 0
        else "供货能力仅按已返回核心产能字段观察；缺失字段不得由渠道、招聘或工厂规模标签替代。"
    )
    return {
        "feature": "供货证据与司法暴露",
        "evidence": "、".join(parts) + "。",
        "interpretation": interp,
    }


def insight_account_financial(data: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    factory = _factory(data)
    base = _base(data)
    op = _operation(data)
    account = _pick(factory, "accountPeriodRisk", "账期风险")
    paid = _ratio_pct(_pick(base, "资本实缴率", "实缴率"))
    fin = _i(op.get("financing_count"))
    if account is None and paid is None and fin is None:
        return None
    parts = []
    if account is not None:
        parts.append(f"数据产品账期标签「{account}」")
    if paid is not None:
        parts.append(f"工商实缴率 {paid:.0f}%")
    if fin is not None:
        parts.append(f"融资记录 {fin} 轮")
    return {
        "feature": "资本与账期公开线索",
        "evidence": "、".join(parts) + "。",
        "interpretation": "缺少审计财务、现金流、应收账款账龄和偿债指标，不能据此评价财务稳健或宣称账期风险可控。",
    }


def insight_channel_competition(data: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    channel = _channel(data)
    search_total = _i(channel.get("search_total"))
    financial = channel.get("financialStat") or {}
    sales = channel.get("salesStat") or {}
    if search_total is None and not financial and not sales:
        return None
    parts = []
    if search_total is not None:
        parts.append(f"渠道关联搜索返回 {search_total} 条")
    if isinstance(financial, dict) and financial.get("categoryCount") is not None:
        parts.append(f"财务分类样本 {financial.get('categoryCount')}")
    if isinstance(sales, dict) and sales.get("categoryCount") is not None:
        parts.append(f"销售分类样本 {sales.get('categoryCount')}")
    return {
        "feature": "渠道关联搜索事实",
        "evidence": "、".join(parts) + "。",
        "interpretation": "该数据来自渠道关联搜索/统计，记录与目标法人的关系尚未逐条确认；不作渠道领先、覆盖能力或供货能力结论。",
    }


def insight_capacity_operation(data: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    factory = _factory(data)
    op = _operation(data)
    assembly = _i(factory.get("assemblyLine"))
    production = _f(
        factory.get("monthlyProductionAmountValue")
        or factory.get("monthlyProductionAmountValue_caps")
    )
    staff = _i(factory.get("boarderStaffNumber"))
    devices = len(factory.get("mainDeviceList") or [])
    if all(v in (None, 0) for v in (assembly, production, staff, devices)):
        return None
    scale = op.get("scale") or {}
    parts = []
    if assembly is not None:
        parts.append(f"产线 {assembly} 条")
    if production is not None:
        parts.append(f"月产能 {production:g}")
    if staff is not None:
        parts.append(f"生产人员 {staff}")
    if devices:
        parts.append(f"设备记录 {devices} 项")
    if _pick(scale, "staff", "人员规模", "enterpriseScale"):
        parts.append(
            f"企业人员规模 {_pick(scale, 'staff', '人员规模', 'enterpriseScale')}"
        )
    return {
        "feature": "产能证据与经营规模",
        "evidence": "、".join(parts) + "。",
        "interpretation": "核心产能字段已返回，可供人工核验；仍需确认工厂记录与目标法人的统一社会信用代码关系、产能时点和实际利用率。",
    }


def _holder_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for h in _holders(data)[:15]:
        ratio = _pick(h, "持股比例", "ratio", "占比")
        sub = _pick(h, "认缴金额", "subscriptionDetail", "认缴", "认缴/实缴")
        if isinstance(sub, dict):
            sub = sub.get("amount") or sub.get("value")
        paid = _pick(h, "实缴金额", "payAmount", "实缴", "paidAmount", "认缴/实缴")
        rows.append(
            {
                "股东名称": str(
                    _pick(h, "股东名称", "name", "名称", "holderName") or "-"
                ),
                "持股比例": format_source_ratio(ratio),
                "认缴金额": _amount_text(sub),
                "实缴金额": _amount_text(paid),
                "股东类型": str(
                    _pick(h, "股东类型", "holderType", "entityType") or "-"
                ),
            }
        )
    return rows


def _amount_text(value: Any) -> str:
    """Readable amount for holder/investment tables (handles JSON amount dicts)."""
    if value in (None, "", "-"):
        return "-"
    if isinstance(value, dict):
        val = value.get("value") or value.get("amount")
        coin = value.get("coinType") or ""
        if val is None:
            return "-"
        try:
            fv = float(val)
            if fv >= 1e8:
                return f"{coin} {fv / 1e8:.2f}亿".strip()
            if fv >= 1e4:
                return f"{coin} {fv / 1e4:.0f}万".strip()
            return f"{coin} {fv:.0f}".strip()
        except (TypeError, ValueError):
            return f"{coin} {val}".strip()
    # bare number string
    try:
        fv = float(str(value).replace(",", ""))
        if fv >= 1e8:
            return f"人民币 {fv / 1e8:.2f}亿"
        if fv >= 1e4:
            return f"人民币 {fv / 1e4:.0f}万"
        return f"人民币 {fv:.0f}"
    except (TypeError, ValueError):
        return str(value)


def _investment_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for inv in _investments(data)[:15]:
        iratio = _pick(inv, "ratio", "持股比例", "占股比例", "投资比例")
        rows.append(
            {
                "被投资企业": str(
                    _pick(inv, "name", "企业名称", "对外投资企业", "被投资企业") or "-"
                ),
                "持股比例": format_source_ratio(iratio),
                "经营状态": str(_pick(inv, "operStatus", "经营状态", "状态") or "-"),
                "成立日期": str(_pick(inv, "foundTime", "成立日期", "成立时间") or "-"),
                "注册资本": _amount_text(
                    _pick(
                        inv, "subscriptionAmount", "投资金额", "regCapital", "注册资本"
                    )
                ),
            }
        )
    return rows


def _litigation_summary_text(data: Mapping[str, Any]) -> str:
    s = _litigation_summary(data)
    parts = []
    if s["hearings"]:
        parts.append(f"开庭公告 {s['hearings']} 条")
    if s["executed"]:
        parts.append(f"被执行 {s['executed']} 条")
    if s["case_count"]:
        parts.append(f"涉诉 {s['case_count']} 起")
    return "、".join(parts) if parts else "无显著诉讼风险"


def _channel_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """渠道搜索结果明细."""
    channel = _channel(data)
    rows = []
    for c in channel.get("search_list", [])[:20]:
        if not isinstance(c, dict):
            continue
        rows.append(
            {
                "渠道名称": str(_pick(c, "channelName", "name", "渠道名称") or "-"),
                "渠道类型": str(_pick(c, "channelType", "type", "渠道类型") or "-"),
                "合作状态": str(_pick(c, "status", "合作状态") or "-"),
            }
        )
    return rows


def _factory_profile_rows(data: Mapping[str, Any]) -> Dict[str, str]:
    """工厂概况 KV."""
    factory = _factory(data)
    out: Dict[str, str] = {}
    if factory.get("factoryScale"):
        out["工厂规模"] = str(factory["factoryScale"])
    if factory.get("factoryAddress"):
        out["工厂地址"] = str(factory["factoryAddress"])
    reg_cap = _pick(factory, "regCapital", "注册资本")
    if reg_cap:
        out["注册资本"] = str(reg_cap)
    production = _pick(
        factory,
        "monthlyProductionAmountValue",
        "monthlyProductionAmountValue_caps",
        "月产能",
    )
    if production:
        out["月产能"] = str(production)
    if factory.get("accountPeriodRisk"):
        out["账期风险"] = str(factory["accountPeriodRisk"])
    types = factory.get("factoryTypeList")
    if isinstance(types, list) and types:
        out["工厂类型"] = "、".join(str(t) for t in types if t)
    return out


def _factory_capabilities_rows(data: Mapping[str, Any]) -> Dict[str, str]:
    """工厂产能能力 KV."""
    factory = _factory(data)
    out: Dict[str, str] = {}
    if factory.get("assemblyLine"):
        out["产线数"] = str(factory["assemblyLine"])
    if factory.get("boarderStaffNumber"):
        out["普工人数"] = str(factory["boarderStaffNumber"])
    if factory.get("inspectionStaffNumber"):
        out["质检人数"] = str(factory["inspectionStaffNumber"])
    devices = factory.get("mainDeviceList")
    if isinstance(devices, list) and devices:
        out["主要设备"] = "、".join(str(d) for d in devices if d)
    if factory.get("managementSystemCertification"):
        out["管理体系认证"] = str(factory["managementSystemCertification"])
    production_caps = _pick(factory, "monthlyProductionAmountValue_caps", "月产能_2")
    if production_caps:
        out["月产能"] = str(production_caps)
    return out


def _factory_product_rows(data: Mapping[str, Any]) -> Dict[str, str]:
    """工厂产品统计 KV."""
    factory = _factory(data)
    out: Dict[str, str] = {}
    if factory.get("serviceBrandCount"):
        out["服务品牌数"] = str(factory["serviceBrandCount"])
    if factory.get("mainProductCount"):
        out["主要产品数"] = str(factory["mainProductCount"])
    tags = factory.get("tagNames")
    if isinstance(tags, list) and tags:
        out["产品标签"] = "、".join(str(t) for t in tags if t)
    return out


def _specialty_score_rows(scores: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for _key, label, v in scores.get("items", []):
        if v is not None:
            grade = (
                "优" if v >= 75 else ("良" if v >= 55 else ("中" if v >= 35 else "弱"))
            )
            rows.append({"评估维度": label, "评分": str(v), "等级": grade})
    return rows


# --------------------------------------------------------------------------- #
# Verdict
# --------------------------------------------------------------------------- #
def build_verdict(data: Mapping[str, Any], scores: Mapping[str, Any]) -> Dict[str, Any]:
    """供应商准入结论: 综合判定 + 关键关注点."""
    risk = _risk(data)
    concerns: List[str] = []
    blockers: List[str] = []

    n_vio = len(risk.get("serious_violations") or [])
    n_res = (
        risk.get("restrictions_total")
        if risk.get("restrictions_total") is not None
        else len(risk.get("restrictions") or [])
    )
    n_pen = _i(risk.get("penalties_total"))
    if n_pen is None:
        n_pen = len(risk.get("penalties") or [])
    n_ano = (
        risk.get("anomalies_total")
        if risk.get("anomalies_total") is not None
        else len(risk.get("anomalies") or [])
    )
    risk_level_text = str(risk.get("level") or "")

    if n_vio:
        blockers.append(f"严重违法记录 {n_vio} 条")
    if n_res:
        blockers.append(f"限制高消费记录 {n_res} 条")
    if n_pen >= 3:
        concerns.append(f"行政处罚 {n_pen} 条")
    if n_ano:
        concerns.append(f"经营异常 {n_ano} 条")
    hearings = _i(risk.get("court_hearings_total"))
    if hearings is not None and hearings >= 100:
        blockers.append(f"开庭公告 {hearings} 条，需人工司法核验")
    elif hearings:
        concerns.append(f"开庭公告 {hearings} 条")
    # 风险判断：优先采信风险等级文本，回退到数值
    if risk_level_text:
        if "高" in risk_level_text or "严重" in risk_level_text:
            blockers.append(f"风险等级「{risk_level_text}」")
        elif "中" in risk_level_text:
            concerns.append(f"风险等级「{risk_level_text}」")

    # 供货能力关注
    supply = score_supply_capability(data)
    if supply is not None and supply < 40:
        concerns.append("供货能力偏弱")

    # 账期风险关注
    factory = _factory(data)
    account_risk = _pick(factory, "accountPeriodRisk", "账期风险")
    if account_risk and ("高" in account_risk or "严重" in account_risk):
        concerns.append(f"账期风险「{account_risk}」")

    avg = scores.get("average")
    if avg is None:
        level = "不予综合评级" if blockers else "数据不足"
        recommendation = "人工司法核验" if blockers else "需补充数据"
        evidence_note = (
            "、".join((blockers + concerns)[:4]) or "主体确认、关键域或工具调用证据不足"
        )
        summary = f"评级门禁未满足，不予综合评级。需核验：{evidence_note}。"
    elif blockers:
        level = "不建议合作"
        recommendation = "不建议合作" if len(blockers) >= 2 else "需深入调查"
        summary = f"发现 {len(blockers)} 项重大风险阻断项（{'、'.join(blockers)}），供应商准入风险较高，建议审慎决策。"
    elif avg is not None and avg >= 72 and not concerns:
        level = "推荐准入"
        recommendation = "推荐准入"
        summary = f"供应商专项评分均值 {avg}，各维度表现稳健，供货能力与合规健康度良好，建议优先合作。"
    elif avg is not None and avg >= 50:
        level = "附条件准入"
        recommendation = "附条件准入"
        summary = f"供应商专项评分均值 {avg}，存在 {len(concerns)} 项需关注事项（{'、'.join(concerns[:3])}），建议设置风险缓释条款或降低合作规模。"
    elif avg is not None:
        level = "需深入调查"
        recommendation = "需深入调查"
        summary = (
            f"供应商专项评分均值 {avg} 偏低，建议补充实地考察与更多维度数据深度调查。"
        )
    else:
        level = "数据不足"
        recommendation = "需补充数据"
        summary = "多维数据覆盖不足，无法形成充分评估结论，建议补充更多维度数据。"

    return {
        "recommendation": recommendation,
        "level": level,
        "summary": summary,
        "blockers": blockers,
        "key_concerns": concerns[:6],
        "specialty_average": avg,
    }


# --------------------------------------------------------------------------- #
# Main entry
# --------------------------------------------------------------------------- #
def analyze(data: Mapping[str, Any]) -> Dict[str, Any]:
    """Run full cross-domain analysis, returning all artifacts for the report."""
    scores = specialty_scores(data)
    insight_fns = [
        insight_supply_risk,
        insight_account_financial,
        insight_channel_competition,
        insight_capacity_operation,
    ]
    cross_insights: List[Dict[str, Any]] = []
    for fn in insight_fns:
        ins = fn(data)
        if ins:
            cross_insights.append(ins)

    verdict = build_verdict(data, scores)
    base = _base(data)

    # Cross metrics (top-level indicator cards)
    metrics: List[Dict[str, Any]] = []
    risk_score = _i(_risk(data).get("score"))
    if risk_score is not None:
        metrics.append(
            {
                "label": "上游风险评分",
                "value": str(risk_score),
                "hint": "上游评分；方向以同次返回等级为准",
                "delta": _risk(data).get("level") or "",
            }
        )
    inv_n = _risk(data).get("investments_total") or len(_investments(data))
    if inv_n:
        metrics.append(
            {
                "label": "对外投资",
                "value": str(inv_n),
                "hint": "关联方数量（风险传导面）",
            }
        )
    if scores.get("average") is not None:
        metrics.append(
            {
                "label": "供应商综合评分",
                "value": str(scores["average"]),
                "hint": f"{len(scores['valid'])} 项有效专项观察均值",
                "delta": verdict["level"],
            }
        )
    # 供货能力指标
    supply = score_supply_capability(data)
    if supply is not None:
        metrics.append(
            {
                "label": "产能证据观察",
                "value": str(supply),
                "hint": "仅基于已返回的产线/生产人员/设备/月产能字段",
            }
        )
    # 合规指标
    n_pen = len(_risk(data).get("penalties") or [])
    if n_pen:
        metrics.append(
            {"label": "行政处罚", "value": str(n_pen), "hint": "行政处罚记录数"}
        )
    # 财务指标
    reg = _pick(base, "注册资本", "regCapital", "regCapitalValue")
    if reg:
        metrics.append(
            {"label": "注册资本", "value": str(reg), "hint": "工商登记注册资本"}
        )
    paid_rate = _ratio_pct(_pick(base, "资本实缴率", "实缴率"))
    if paid_rate is not None:
        metrics.append(
            {
                "label": "资本实缴率",
                "value": f"{paid_rate:.0f}%",
                "hint": "实缴资本/注册资本比例",
            }
        )
    fin_n = _i(_operation(data).get("financing_count"))
    if fin_n:
        metrics.append(
            {"label": "融资轮次", "value": str(fin_n), "hint": "历史融资轮次"}
        )
    # 渠道指标
    channel_count = _i(_channel(data).get("channelCount"))
    if channel_count:
        metrics.append(
            {
                "label": "渠道总数",
                "value": str(channel_count),
                "hint": "销售/合作渠道数量",
            }
        )
    peer_avg = _i(_channel(data).get("peerAvgChannelCount"))
    if peer_avg:
        metrics.append(
            {"label": "同行平均渠道", "value": str(peer_avg), "hint": "行业平均水平"}
        )
    # 工厂指标
    assembly_line = _i(_factory(data).get("assemblyLine"))
    if assembly_line:
        metrics.append(
            {"label": "产线数", "value": str(assembly_line), "hint": "工厂生产线数量"}
        )
    boarder_staff = _i(_factory(data).get("boarderStaffNumber"))
    if boarder_staff:
        metrics.append(
            {
                "label": "普工人数",
                "value": str(boarder_staff),
                "hint": "工厂生产人员规模",
            }
        )
    account_risk = _pick(_factory(data), "accountPeriodRisk", "账期风险")
    if account_risk:
        metrics.append(
            {
                "label": "数据产品账期标签",
                "value": str(account_risk),
                "hint": "上游公开数据标签，非审计财务或应收账龄结论",
            }
        )
    # 招聘指标
    cur_hire = _i(_recruitment(data).get("current"))
    if cur_hire is not None:
        metrics.append(
            {"label": "在招岗位", "value": str(cur_hire), "hint": "招聘活跃度信号"}
        )
    # 风险计数指标（供应商评估核心信号）— 优先用 MCP total
    risk = _risk(data)
    res_n = risk.get("restrictions_total") or len(risk.get("restrictions") or [])
    if res_n:
        metrics.append(
            {
                "label": "限制高消费",
                "value": str(res_n),
                "hint": "被执行限高记录数",
                "delta": "▼" if res_n >= 5 else "",
            }
        )
    hearing_n = risk.get("court_hearings_total")
    if hearing_n:
        metrics.append(
            {"label": "开庭公告", "value": str(hearing_n), "hint": "诉讼开庭记录总数"}
        )
    ano_n = risk.get("anomalies_total") or len(risk.get("anomalies") or [])
    if ano_n:
        metrics.append(
            {"label": "经营异常", "value": str(ano_n), "hint": "经营异常名录记录"}
        )
    holder_n = len(_holders(data))
    if holder_n:
        metrics.append(
            {"label": "股东数量", "value": str(holder_n), "hint": "工商公示股东数"}
        )
    found_year = _pick(base, "成立日期", "foundTime", "成立时间")
    if found_year and str(found_year)[:4].isdigit():
        import datetime as _dt

        age = _dt.datetime.now().year - int(str(found_year)[:4])
        if age >= 0:
            metrics.append(
                {
                    "label": "成立年限",
                    "value": f"{age} 年",
                    "hint": f"成立于 {str(found_year)[:4]} 年",
                }
            )
    for _key, label, v in scores["valid"]:
        metrics.append({"label": label, "value": str(v), "hint": "供应商专项评分"})

    # Detail sections
    section_specs: List[Dict[str, Any]] = []
    section_data: Dict[str, Any] = {}

    holder_rows = _holder_rows(data)
    if holder_rows:
        section_specs.append(
            {
                "key": "se_holders",
                "title": "股东出资结构",
                "kind": "table",
                "note": "股东持股比例与实缴情况（资本充实性核查基础）",
                "columns": [
                    ("股东名称", "股东名称"),
                    ("持股比例", "持股比例"),
                    ("认缴金额", "认缴金额"),
                    ("实缴金额", "实缴金额"),
                    ("股东类型", "股东类型"),
                ],
            }
        )
        section_data["se_holders"] = holder_rows

    invest_rows = _investment_rows(data)
    if invest_rows:
        inv_total = _risk(data).get("investments_total") or len(_investments(data))
        section_specs.append(
            {
                "key": "se_investments",
                "title": "对外投资清单（关联方敞口）",
                "kind": "table",
                "note": f"报告总量 {inv_total} 家，当前列表展示 {min(len(_investments(data)), 15)} 家；仅表示关联暴露面，未核验关联方风险传导",
                "columns": [
                    ("被投资企业", "被投资企业"),
                    ("持股比例", "持股比例"),
                    ("经营状态", "经营状态"),
                    ("成立日期", "成立日期"),
                    ("注册资本", "注册资本"),
                ],
            }
        )
        section_data["se_investments"] = invest_rows

    score_rows = _specialty_score_rows(scores)
    if score_rows:
        section_specs.append(
            {
                "key": "se_specialty",
                "title": "供应商专项评分矩阵",
                "kind": "table",
                "note": "产能证据、司法合规与风险隔离观察；缺少审计财务时财务稳健性不评分",
                "columns": [
                    ("评估维度", "评估维度"),
                    ("评分", "评分"),
                    ("等级", "等级"),
                ],
            }
        )
        section_data["se_specialty"] = score_rows

    return {
        "metrics": metrics,
        "insights": cross_insights,
        "specialty_scores": {
            "items": [
                {"key": key, "label": label, "score": value}
                for key, label, value in scores["items"]
            ],
            "average": scores["average"],
        },
        "verdict": verdict,
        "section_specs": section_specs,
        "section_data": section_data,
    }
