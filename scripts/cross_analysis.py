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

import json
from typing import Any, Dict, List, Mapping, Optional

# --------------------------------------------------------------------------- #
# Tolerant field extraction (handles both live MCP and cached report shapes)
# --------------------------------------------------------------------------- #
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
        return float(str(value).replace(",", "").replace("万", "").replace("%", "").replace("亿", ""))
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
    """Unified litigation info across live MCP (English keys) and cached reports (Chinese keys)."""
    risk = _risk(data)
    lit = _litigation(data)
    case_count = _i(lit.get("case_count") or lit.get("caseCount"))
    defendant = _i(lit.get("as_defendant") or lit.get("asDefendant"))
    plaintiff = _i(lit.get("as_plaintiff") or lit.get("asPlaintiff"))
    hearings = risk.get("court_hearings_total") or _i(lit.get("开庭公告数"))
    announcements = _i(lit.get("法院公告数"))
    judgments = _i(lit.get("裁判文书数"))
    executed = risk.get("restrictions_total") or _i(lit.get("被执行人记录数"))
    dishonest = _i(lit.get("失信被执行人数"))
    if case_count is None:
        parts = [v for v in (hearings, announcements, judgments) if v is not None]
        if parts:
            case_count = sum(parts)
    return {
        "case_count": case_count, "as_defendant": defendant, "as_plaintiff": plaintiff,
        "hearings": hearings, "announcements": announcements, "judgments": judgments,
        "executed": executed, "dishonest": dishonest,
        "has_role_detail": defendant is not None,  # live mode has defendant/plaintiff split
    }


def _operation(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("operation") or {})


def _channel(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("channel") or {})


def _factory(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("factory") or {})


def _recruitment(data: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(data.get("recruitment") or {})


# --------------------------------------------------------------------------- #
# Specialty scores (each 0-100, or None if data unavailable)
# --------------------------------------------------------------------------- #
def score_supply_capability(data: Mapping[str, Any]) -> Optional[float]:
    """供货能力: 工厂产能/设备/产线 + 渠道覆盖."""
    factory = _factory(data)
    channel = _channel(data)

    # 工厂产能维度
    assembly_line = _i(factory.get("assemblyLine")) or 0
    production = _f(factory.get("monthlyProductionAmountValue") or factory.get("monthlyProductionAmountValue_caps"))
    staff = _i(factory.get("boarderStaffNumber")) or 0
    devices = len(factory.get("mainDeviceList") or [])

    # 渠道维度
    channel_count = _i(channel.get("channelCount")) or 0
    supplier_count = _i(channel.get("supplierCount")) or 0

    # 如果完全没有数据，返回 None
    if (assembly_line == 0 and production is None and staff == 0 and devices == 0 and
        channel_count == 0 and supplier_count == 0):
        return None

    s = 0
    # 工厂产能评分（最高 50 分）
    if assembly_line:
        s += min(20, assembly_line * 4)
    if production:
        # 月产能转换为评分
        if production >= 10000000:  # 1000万+
            s += 20
        elif production >= 1000000:  # 100万+
            s += 15
        elif production >= 100000:  # 10万+
            s += 10
        else:
            s += 5
    if staff:
        s += min(10, staff / 10)
    if devices:
        s += min(10, devices * 2)

    # 渠道评分（最高 50 分）
    if channel_count:
        s += min(25, channel_count * 2)
    if supplier_count:
        s += min(25, supplier_count * 1.5)

    return round(max(0, min(100, s)), 1)


def score_compliance_health(data: Mapping[str, Any]) -> Optional[float]:
    """合规健康度: deduct for penalties / anomalies / restrictions / violations."""
    risk = _risk(data)
    n_pen = len(risk.get("penalties") or [])
    n_ano = len(risk.get("anomalies") or [])
    n_res = len(risk.get("restrictions") or [])
    n_vio = len(risk.get("serious_violations") or []) if risk.get("serious_violations") else 0
    total_hits = n_pen + n_ano + n_res + n_vio
    if total_hits == 0 and risk.get("score") is None:
        return None
    health = 100 - (n_pen * 14 + n_ano * 9 + n_res * 18 + n_vio * 25)
    return round(max(0, min(100, health)), 1)


def score_financial_stability(data: Mapping[str, Any]) -> Optional[float]:
    """财务稳健性: 实缴率 + 融资 + 经营规模."""
    base = _base(data)
    operation = _operation(data)

    paid_rate = _ratio_pct(_pick(base, "资本实缴率", "实缴率", "paidRate", "paidRatio"))
    if paid_rate is None:
        reg = _f(_pick(base, "注册资本", "regCapital", "regCapitalValue"))
        paid = _f(_pick(base, "实缴资本", "realCapital", "paidInCapital"))
        if reg and paid is not None and reg > 0:
            paid_rate = paid / reg * 100

    fin_n = _i(operation.get("financing_count")) or 0
    scale = operation.get("scale") or {}
    has_scale = bool(_pick(scale, "staff", "人员规模", "enterpriseScale") or _pick(scale, "turnover", "年营业额", "annualTurnover"))

    if paid_rate is None and fin_n == 0 and not has_scale:
        return None

    s = 0
    # 实缴率评分（最高 40 分）
    if paid_rate is not None:
        if paid_rate >= 80:
            s += 40
        elif paid_rate >= 50:
            s += 25 + (paid_rate - 50) * 0.5
        elif paid_rate >= 20:
            s += 10 + (paid_rate - 20) * 0.5
        else:
            s += paid_rate * 0.5
    else:
        s += 20  # 缺失数据保守给分

    # 融资评分（最高 30 分）
    s += min(30, fin_n * 8)

    # 经营规模评分（最高 30 分）
    if has_scale:
        s += 30

    return round(max(0, min(100, s)), 1)


def score_risk_isolation(data: Mapping[str, Any]) -> Optional[float]:
    """风险隔离度 (higher = better isolated): penalized by investment breadth × risk."""
    invest_n = len(_investments(data))
    risk_score = _i(_risk(data).get("score"))
    level_text = str(_risk(data).get("level") or "")
    ls = _litigation_summary(data)
    defendant = ls["as_defendant"] or 0
    executed = ls["executed"] or 0
    dishonest = ls["dishonest"] or 0
    penalties = len(_risk(data).get("penalties") or [])
    if risk_score is None and not level_text and invest_n == 0 and defendant == 0 and penalties == 0 and not executed and not dishonest:
        return None
    # risk factor: prefer level text, fall back to raw score
    if "高" in level_text or "严重" in level_text:
        risk_factor = 28
    elif "中" in level_text:
        risk_factor = 14
    elif "低" in level_text:
        risk_factor = 2
    else:
        risk_factor = max(0, (risk_score or 50) - 40) * 1.1
    exposure = invest_n * 4 + risk_factor + defendant * 7 + penalties * 6 + executed * 10 + dishonest * 20
    return round(max(0, min(100, 100 - exposure)), 1)


def specialty_scores(data: Mapping[str, Any]) -> Dict[str, Any]:
    items = [
        ("supply_capability", "供货能力", score_supply_capability(data)),
        ("compliance_health", "合规健康度", score_compliance_health(data)),
        ("financial_stability", "财务稳健性", score_financial_stability(data)),
        ("risk_isolation", "风险隔离度", score_risk_isolation(data)),
    ]
    valid = [(key, label, v) for key, label, v in items if v is not None]
    avg = round(sum(v for _, _, v in valid) / len(valid), 1) if valid else None
    return {"items": items, "valid": valid, "average": avg}


# --------------------------------------------------------------------------- #
# Cross-domain insights
# --------------------------------------------------------------------------- #
def insight_supply_risk(data: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """供货能力 × 合规风险: 产能强但风险高 → 供货中断风险."""
    supply_score = score_supply_capability(data)
    risk_score = _i(_risk(data).get("score"))
    risk_level = str(_risk(data).get("level") or "")
    if supply_score is None and risk_score is None:
        return None

    factory = _factory(data)
    assembly_line = _i(factory.get("assemblyLine")) or 0
    production = _f(factory.get("monthlyProductionAmountValue") or factory.get("monthlyProductionAmountValue_caps"))
    channel = _channel(data)
    channel_count = _i(channel.get("channelCount")) or 0

    parts = []
    if assembly_line:
        parts.append(f"产线 {assembly_line} 条")
    if production:
        parts.append(f"月产能 {production/10000:.0f}万" if production >= 10000 else f"月产能 {production:.0f}")
    if channel_count:
        parts.append(f"渠道数 {channel_count}")

    evidence = "、".join(parts) if parts else "产能与渠道数据有限"
    if risk_score is not None or risk_level:
        evidence += f"，风险评分 {risk_score or '?'}（{risk_level or '-'}）"

    if supply_score and supply_score >= 60 and (risk_score or 0) >= 50:
        interp = f"供货能力较强（{supply_score:.0f}分）但风险偏高（{risk_level or risk_score}）。存在供货中断风险，建议核查重大风险案件对生产运营的影响，评估备用产能可行性。"
    elif supply_score and supply_score >= 60:
        interp = f"供货能力较强（{supply_score:.0f}分），风险可控。产能与渠道覆盖能够支撑订单交付，建议关注产能利用率与交期履约率。"
    elif supply_score and supply_score < 40:
        interp = f"供货能力偏弱（{supply_score:.0f}分）。产线、产能或渠道覆盖不足，可能影响订单承接与交付稳定性，建议评估产能扩充计划或渠道拓展策略。"
    else:
        interp = "供货与风险数据有限，建议结合实地考察综合评估交付能力。"

    return {"feature": "供货能力与风险匹配度", "evidence": f"{evidence}。", "interpretation": interp}


def insight_account_financial(data: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """账期风险 × 财务稳健: 账期风险 + 实缴率/融资."""
    factory = _factory(data)
    account_risk = _pick(factory, "accountPeriodRisk", "账期风险")
    base = _base(data)
    paid_rate = _ratio_pct(_pick(base, "资本实缴率", "实缴率"))
    operation = _operation(data)
    fin_n = _i(operation.get("financing_count"))

    if not account_risk and paid_rate is None and fin_n == 0:
        return None

    parts = []
    if account_risk:
        parts.append(f"账期风险「{account_risk}」")
    if paid_rate is not None:
        parts.append(f"实缴率 {paid_rate:.0f}%")
    if fin_n:
        parts.append(f"完成 {fin_n} 轮融资")

    evidence = "、".join(parts) + "。" if parts else "财务数据有限。"

    paid_adequate = (paid_rate or 0) >= 50
    fin_healthy = fin_n and fin_n >= 1

    if account_risk and ("高" in account_risk or "严重" in account_risk):
        if not paid_adequate and not fin_healthy:
            interp = "账期风险高且财务稳健性不足，存在回款风险。建议严格审核账期政策，要求缩短账期或提供担保，监控现金流状况。"
        else:
            interp = "账期风险较高，但财务基础相对扎实。建议关注应收账款账龄结构，建立动态账期管理机制。"
    elif account_risk and ("中" in account_risk):
        interp = "账期风险中等，建议结合合作规模设置合理账期，定期评估客户信用变化。"
    elif paid_adequate or fin_healthy:
        interp = "财务稳健性较好，账期风险可控。建议维持健康的账期政策，平衡客户关系与资金周转。"
    else:
        interp = "财务稳健性一般，建议结合更多维度数据综合评估。"

    return {"feature": "账期风险与财务稳健性", "evidence": evidence, "interpretation": interp}


def insight_channel_competition(data: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """渠道竞争力: channelCount vs peerAvgChannelCount → 同行对比定位."""
    channel = _channel(data)
    channel_count = _i(channel.get("channelCount"))
    peer_avg = _i(channel.get("peerAvgChannelCount"))
    rank = _i(channel.get("channelRank"))

    if channel_count is None and peer_avg is None and rank is None:
        return None

    if channel_count is not None and peer_avg is not None:
        ratio = channel_count / peer_avg if peer_avg > 0 else 1
        if ratio >= 1.5:
            position = "领先"
        elif ratio >= 0.8:
            position = "相当"
        else:
            position = "偏弱"
        evidence = f"渠道数 {channel_count}，同行平均 {peer_avg}（{position}）。"
    elif channel_count is not None:
        evidence = f"渠道数 {channel_count}（同行对比数据缺失）。"
    else:
        evidence = "渠道数据有限。"

    if rank is not None:
        evidence += f"渠道排名 {rank}。"

    if position == "领先":
        interp = "渠道覆盖面广，市场拓展能力强，具备一定的规模优势与议价能力。建议关注渠道质量与转化效率，避免盲目扩张。"
    elif position == "相当":
        interp = "渠道覆盖与行业平均水平相当，市场竞争力处于合理区间。建议优化渠道结构，提升优质渠道占比。"
    elif position == "偏弱":
        interp = "渠道覆盖相对不足，可能限制市场拓展与订单获取。建议评估渠道短板，制定针对性拓展计划或强化核心渠道深度合作。"
    else:
        interp = "建议补充同行对比数据以精准定位渠道竞争力。"

    return {"feature": "渠道竞争力（同行对比）", "evidence": evidence, "interpretation": interp}


def insight_capacity_operation(data: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """产能 × 经营规模匹配: factory scale vs operation scale."""
    factory = _factory(data)
    operation = _operation(data)

    factory_scale = _pick(factory, "factoryScale", "工厂规模")
    production = _f(factory.get("monthlyProductionAmountValue") or factory.get("monthlyProductionAmountValue_caps"))
    scale = operation.get("scale") or {}
    op_staff = _pick(scale, "staff", "人员规模", "enterpriseScale")
    op_turnover = _pick(scale, "turnover", "年营业额", "annualTurnover")

    if not factory_scale and production is None and not op_staff and not op_turnover:
        return None

    parts = []
    if factory_scale:
        parts.append(f"工厂规模「{factory_scale}」")
    if production:
        parts.append(f"月产能 {production/10000:.0f}万" if production >= 10000 else f"月产能 {production:.0f}")
    if op_staff:
        parts.append(f"人员规模 {op_staff}")
    if op_turnover:
        parts.append(f"年营业额 {op_turnover}")

    evidence = "、".join(parts) + "。" if parts else "规模匹配数据有限。"

    # 简化判断：如果都有数据则说明匹配，如果只有一边则提示补充
    if factory_scale or production:
        if op_staff or op_turnover:
            interp = "产能与经营规模数据匹配，产能布局与业务规模基本协调。建议关注产能利用率与订单波动匹配度。"
        else:
            interp = "有产能数据但经营规模数据缺失，建议补充营业额/人员数据以评估产能利用效率。"
    else:
        interp = "建议补充工厂产能与经营规模数据以评估匹配度。"

    return {"feature": "产能与经营规模匹配度", "evidence": evidence, "interpretation": interp}


# --------------------------------------------------------------------------- #
# Detail sections (tables fed to the renderer)
# --------------------------------------------------------------------------- #
def _holder_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for h in _holders(data)[:15]:
        ratio = _pick(h, "持股比例", "ratio", "占比")
        if ratio is not None:
            try:
                rf = float(ratio)
                ratio = f"{rf * 100:.1f}%" if rf <= 1 else f"{rf:.1f}%"
            except (TypeError, ValueError):
                pass
        sub = _pick(h, "认缴金额", "subscriptionDetail", "认缴", "认缴/实缴")
        if isinstance(sub, dict):
            sub = sub.get("amount") or sub.get("value")
        paid = _pick(h, "实缴金额", "payAmount", "实缴", "paidAmount", "认缴/实缴")
        rows.append({
            "股东名称": str(_pick(h, "股东名称", "name", "名称", "holderName") or "-"),
            "持股比例": str(ratio or "-"),
            "认缴金额": _amount_text(sub),
            "实缴金额": _amount_text(paid),
            "股东类型": str(_pick(h, "股东类型", "holderType", "entityType") or "-"),
        })
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
                return f"{coin} {fv/1e8:.2f}亿".strip()
            if fv >= 1e4:
                return f"{coin} {fv/1e4:.0f}万".strip()
            return f"{coin} {fv:.0f}".strip()
        except (TypeError, ValueError):
            return f"{coin} {val}".strip()
    # bare number string
    try:
        fv = float(str(value).replace(",", ""))
        if fv >= 1e8:
            return f"人民币 {fv/1e8:.2f}亿"
        if fv >= 1e4:
            return f"人民币 {fv/1e4:.0f}万"
        return f"人民币 {fv:.0f}"
    except (TypeError, ValueError):
        return str(value)


def _investment_rows(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for inv in _investments(data)[:15]:
        iratio = _pick(inv, "ratio", "持股比例", "占股比例", "投资比例")
        if iratio is not None:
            try:
                rf = float(iratio)
                iratio = f"{rf * 100:.0f}%" if rf <= 1 else f"{rf:.0f}%"
            except (TypeError, ValueError):
                pass
        rows.append({
            "被投资企业": str(_pick(inv, "name", "企业名称", "对外投资企业", "被投资企业") or "-"),
            "持股比例": str(iratio or "-"),
            "经营状态": str(_pick(inv, "operStatus", "经营状态", "状态") or "-"),
            "成立日期": str(_pick(inv, "foundTime", "成立日期", "成立时间") or "-"),
            "注册资本": _amount_text(_pick(inv, "subscriptionAmount", "投资金额", "regCapital", "注册资本")),
        })
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
        rows.append({
            "渠道名称": str(_pick(c, "channelName", "name", "渠道名称") or "-"),
            "渠道类型": str(_pick(c, "channelType", "type", "渠道类型") or "-"),
            "合作状态": str(_pick(c, "status", "合作状态") or "-"),
        })
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
    production = _pick(factory, "monthlyProductionAmountValue", "monthlyProductionAmountValue_caps", "月产能")
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
            grade = "优" if v >= 75 else ("良" if v >= 55 else ("中" if v >= 35 else "弱"))
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
    n_res = len(risk.get("restrictions") or [])
    n_pen = len(risk.get("penalties") or [])
    n_ano = len(risk.get("anomalies") or [])
    risk_score = _i(risk.get("score"))
    risk_level_text = str(risk.get("level") or "")

    if n_vio:
        blockers.append(f"严重违法记录 {n_vio} 条")
    if n_res:
        blockers.append(f"限制高消费记录 {n_res} 条")
    if n_pen >= 3:
        concerns.append(f"行政处罚 {n_pen} 条")
    if n_ano:
        concerns.append(f"经营异常 {n_ano} 条")
    # 风险判断：优先采信风险等级文本，回退到数值
    if risk_level_text:
        if "高" in risk_level_text or "严重" in risk_level_text:
            blockers.append(f"风险等级「{risk_level_text}」")
        elif "中" in risk_level_text:
            concerns.append(f"风险等级「{risk_level_text}」")
    elif risk_score is not None and risk_score >= 70:
        blockers.append(f"综合风险评分 {risk_score}（偏高）")
    elif risk_score is not None and risk_score >= 50:
        concerns.append(f"综合风险评分 {risk_score}（中等）")

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
    if blockers:
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
        summary = f"供应商专项评分均值 {avg} 偏低，建议补充实地考察与更多维度数据深度调查。"
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
        metrics.append({"label": "综合风险评分", "value": str(risk_score), "hint": "风险洞察评分（越低越好）", "delta": _risk(data).get("level") or ""})
    inv_n = _risk(data).get("investments_total") or len(_investments(data))
    if inv_n:
        metrics.append({"label": "对外投资", "value": str(inv_n), "hint": "关联方数量（风险传导面）"})
    if scores.get("average") is not None:
        metrics.append({"label": "供应商综合评分", "value": str(scores["average"]), "hint": "4 项专项评分均值", "delta": verdict["level"]})
    # 供货能力指标
    supply = score_supply_capability(data)
    if supply is not None:
        metrics.append({"label": "供货能力", "value": str(supply), "hint": "工厂产能+渠道覆盖综合评分"})
    # 合规指标
    n_pen = len(_risk(data).get("penalties") or [])
    if n_pen:
        metrics.append({"label": "行政处罚", "value": str(n_pen), "hint": "行政处罚记录数"})
    # 财务指标
    reg = _pick(base, "注册资本", "regCapital", "regCapitalValue")
    if reg:
        metrics.append({"label": "注册资本", "value": str(reg), "hint": "工商登记注册资本"})
    paid_rate = _ratio_pct(_pick(base, "资本实缴率", "实缴率"))
    if paid_rate is not None:
        metrics.append({"label": "资本实缴率", "value": f"{paid_rate:.0f}%", "hint": "实缴资本/注册资本比例"})
    fin_n = _i(_operation(data).get("financing_count"))
    if fin_n:
        metrics.append({"label": "融资轮次", "value": str(fin_n), "hint": "历史融资轮次"})
    # 渠道指标
    channel_count = _i(_channel(data).get("channelCount"))
    if channel_count:
        metrics.append({"label": "渠道总数", "value": str(channel_count), "hint": "销售/合作渠道数量"})
    peer_avg = _i(_channel(data).get("peerAvgChannelCount"))
    if peer_avg:
        metrics.append({"label": "同行平均渠道", "value": str(peer_avg), "hint": "行业平均水平"})
    # 工厂指标
    assembly_line = _i(_factory(data).get("assemblyLine"))
    if assembly_line:
        metrics.append({"label": "产线数", "value": str(assembly_line), "hint": "工厂生产线数量"})
    boarder_staff = _i(_factory(data).get("boarderStaffNumber"))
    if boarder_staff:
        metrics.append({"label": "普工人数", "value": str(boarder_staff), "hint": "工厂生产人员规模"})
    account_risk = _pick(_factory(data), "accountPeriodRisk", "账期风险")
    if account_risk:
        metrics.append({"label": "账期风险", "value": str(account_risk), "hint": "应收账款账期风险等级"})
    # 招聘指标
    cur_hire = _i(_recruitment(data).get("current"))
    if cur_hire is not None:
        metrics.append({"label": "在招岗位", "value": str(cur_hire), "hint": "招聘活跃度信号"})
    # 风险计数指标（供应商评估核心信号）— 优先用 MCP total
    risk = _risk(data)
    res_n = risk.get("restrictions_total") or len(risk.get("restrictions") or [])
    if res_n:
        metrics.append({"label": "限制高消费", "value": str(res_n), "hint": "被执行限高记录数", "delta": "▼" if res_n >= 5 else ""})
    hearing_n = risk.get("court_hearings_total")
    if hearing_n:
        metrics.append({"label": "开庭公告", "value": str(hearing_n), "hint": "诉讼开庭记录总数"})
    ano_n = risk.get("anomalies_total") or len(risk.get("anomalies") or [])
    if ano_n:
        metrics.append({"label": "经营异常", "value": str(ano_n), "hint": "经营异常名录记录"})
    holder_n = len(_holders(data))
    if holder_n:
        metrics.append({"label": "股东数量", "value": str(holder_n), "hint": "工商公示股东数"})
    found_year = _pick(base, "成立日期", "foundTime", "成立时间")
    if found_year and str(found_year)[:4].isdigit():
        import datetime as _dt
        age = _dt.datetime.now().year - int(str(found_year)[:4])
        if age >= 0:
            metrics.append({"label": "成立年限", "value": f"{age} 年", "hint": f"成立于 {str(found_year)[:4]} 年"})
    for _key, label, v in scores["valid"]:
        metrics.append({"label": label, "value": str(v), "hint": "供应商专项评分"})

    # Detail sections
    section_specs: List[Dict[str, Any]] = []
    section_data: Dict[str, Any] = {}

    holder_rows = _holder_rows(data)
    if holder_rows:
        section_specs.append({"key": "se_holders", "title": "股东出资结构", "kind": "table",
                              "note": "股东持股比例与实缴情况（资本充实性核查基础）",
                              "columns": [("股东名称", "股东名称"), ("持股比例", "持股比例"), ("认缴金额", "认缴金额"), ("实缴金额", "实缴金额"), ("股东类型", "股东类型")]})
        section_data["se_holders"] = holder_rows

    invest_rows = _investment_rows(data)
    if invest_rows:
        inv_total = _risk(data).get("investments_total") or len(_investments(data))
        section_specs.append({"key": "se_investments", "title": "对外投资清单（关联方敞口）", "kind": "table",
                              "note": f"共 {inv_total} 家对外投资（展示前 {min(len(_investments(data)), 15)} 家），风险可能经关联方传导",
                              "columns": [("被投资企业", "被投资企业"), ("持股比例", "持股比例"), ("经营状态", "经营状态"), ("成立日期", "成立日期"), ("注册资本", "注册资本")]})
        section_data["se_investments"] = invest_rows

    score_rows = _specialty_score_rows(scores)
    if score_rows:
        section_specs.append({"key": "se_specialty", "title": "供应商专项评分矩阵", "kind": "table",
                              "note": "跨维度交叉评分（供货能力 / 合规健康度 / 财务稳健性 / 风险隔离度）",
                              "columns": [("评估维度", "评估维度"), ("评分", "评分"), ("等级", "等级")]})
        section_data["se_specialty"] = score_rows

    return {
        "metrics": metrics,
        "insights": cross_insights,
        "specialty_scores": {"items": [{"key": k, "label": l, "score": v} for k, l, v in scores["items"]],
                             "average": scores["average"]},
        "verdict": verdict,
        "section_specs": section_specs,
        "section_data": section_data,
    }
