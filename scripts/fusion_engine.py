#!/usr/bin/env python3
"""Enterprise fusion engine: aggregate atomic-skill reports into a scored profile.

This module implements the evidence-scoring model (ported from the reference
industry-chain-processing project) adapted for multi-dimensional enterprise
assessment. Each dimension (patents, risk, bidding, etc.) is scored by its
data richness, evidence strength, and signal quality, then combined into a
composite confidence score.

The engine does NOT call MCP directly — it consumes the JSON outputs of the 21
atomic skills (either freshly generated or pre-existing).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Sequence


# --------------------------------------------------------------------------- #
# Dimension matrix: maps a "fusion dimension" to the atomic skill(s) that feed it
# --------------------------------------------------------------------------- #

DIMENSION_MATRIX: List[Dict[str, Any]] = [
    {
        "dimension": "innovation",
        "label": "创新实力",
        "skills": ["patent-report", "trademark-report", "qualification-report"],
        "weight": 15,
        "description": "专利储备、商标布局、资质认证",
    },
    {
        "dimension": "market_activity",
        "label": "市场活跃度",
        "skills": ["bidding-report", "news-report", "exhibition-report"],
        "weight": 12,
        "description": "招投标参与、舆情健康、展会活动",
    },
    {
        "dimension": "risk_health",
        "label": "风险健康度",
        "skills": ["enterprise-risk-report"],
        "weight": 15,
        "description": "风险评分、诉讼情况、合规状态",
    },
    {
        "dimension": "business_base",
        "label": "工商基础",
        "skills": ["enterprise-report"],
        "weight": 12,
        "description": "注册资本、股权结构、对外投资",
    },
    {
        "dimension": "operations",
        "label": "经营状况",
        "skills": ["enterprise-operation-report", "recruitment-report"],
        "weight": 12,
        "description": "经营规模、融资、招聘活跃度",
    },
    {
        "dimension": "digitalization",
        "label": "数字化程度",
        "skills": ["cloudmigration-report"],
        "weight": 10,
        "description": "上云资产、域名、云支出",
    },
    {
        "dimension": "supply_chain",
        "label": "供应链与渠道",
        "skills": ["factory-channel-report", "factory-insight-report"],
        "weight": 8,
        "description": "渠道能力、工厂产能",
    },
    {
        "dimension": "trade_and_ecommerce",
        "label": "外贸与电商",
        "skills": ["customs-report", "estore-report", "goods-report", "store-report"],
        "weight": 8,
        "description": "出口贸易、网店运营、商品销售",
    },
]

# --------------------------------------------------------------------------- #
# Scenario presets: focused dimension subsets for real business use cases
# --------------------------------------------------------------------------- #

SCENARIO_PRESETS: Dict[str, Dict[str, Any]] = {
    "full": {
        "label": "全维度综合画像",
        "description": "聚合全部 8 个维度，适用于企业全面体检",
        "dimensions": None,  # None = all dimensions
        "title_suffix": "企业综合画像报告",
    },
    "due_diligence": {
        "label": "尽调评估",
        "description": "投资/并购/合作前的风险评估：聚焦合规、财务健康、经营稳定性",
        "dimensions": ["business_base", "risk_health", "operations", "innovation"],
        "weight_overrides": {"business_base": 20, "risk_health": 25, "operations": 15, "innovation": 10},
        "title_suffix": "尽调评估报告",
    },
    "competitive": {
        "label": "竞争分析",
        "description": "竞品技术对比：聚焦创新实力、市场表现、经营规模",
        "dimensions": ["innovation", "market_activity", "operations", "business_base"],
        "weight_overrides": {"innovation": 25, "market_activity": 20, "operations": 15, "business_base": 10},
        "title_suffix": "竞争分析报告",
    },
    "supplier": {
        "label": "供应商评估",
        "description": "评估供应商/合作伙伴可靠性：聚焦合规、供货能力、经营稳定性",
        "dimensions": ["business_base", "risk_health", "supply_chain", "operations"],
        "weight_overrides": {"business_base": 15, "risk_health": 25, "supply_chain": 20, "operations": 15},
        "title_suffix": "供应商评估报告",
    },
    "opportunity": {
        "label": "商机挖掘",
        "description": "销售线索评估：聚焦商业机会、市场活跃度、数字化程度",
        "dimensions": ["market_activity", "operations", "digitalization", "business_base"],
        "weight_overrides": {"market_activity": 25, "operations": 20, "digitalization": 15, "business_base": 10},
        "title_suffix": "商机挖掘报告",
    },
}

# Evidence strength tiers (ported from reference project's evidence-scoring.md)
STRONG_SOURCES = {"primary_records", "patent_titles", "bid_subjects", "risk_cases", "court_records"}
MEDIUM_SOURCES = {"aggregate_stats", "scores", "counts", "trends", "distributions"}
WEAK_SOURCES = {"fuzzy_match", "indirect", "registration_only"}


# --------------------------------------------------------------------------- #
# Data loading: run atomic skills or read existing JSONs
# --------------------------------------------------------------------------- #

def run_atomic_skill(skill_name: str, enterprise: str, skills_dir: str, *, output_dir: str, dry_run: bool = False) -> Optional[Dict[str, Any]]:
    """Run an atomic skill's compose_report.py and return its JSON payload."""
    compose = pathlib.Path(skills_dir) / skill_name / "scripts" / "compose_report.py"
    if not compose.exists():
        return None
    out_json = pathlib.Path(output_dir) / f"{skill_name}.json"
    args = ["python3", str(compose), "--enterprise", enterprise, "--output", str(out_json)]
    if dry_run:
        args.append("--dry-run")
    try:
        subprocess.run(args, capture_output=True, text=True, timeout=200, cwd=str(compose.parent))
    except (subprocess.TimeoutExpired, Exception):
        return None
    if out_json.exists():
        return json.loads(out_json.read_text(encoding="utf-8"))
    return None


def load_existing_report(skill_name: str, reports_dir: str) -> Optional[Dict[str, Any]]:
    """Load a pre-existing atomic skill report JSON."""
    p = pathlib.Path(reports_dir) / f"{skill_name}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


# --------------------------------------------------------------------------- #
# Scoring: per-dimension evidence assessment
# --------------------------------------------------------------------------- #

def _metric_value(report: Mapping[str, Any], label_substr: str) -> Optional[str]:
    """Find a metric value by partial label match."""
    for m in report.get("metrics", []):
        if isinstance(m, dict) and label_substr in str(m.get("label", "")):
            return str(m.get("value", ""))
    return None


def _metric_int(report: Mapping[str, Any], label_substr: str) -> Optional[int]:
    v = _metric_value(report, label_substr)
    if v is None:
        return None
    try:
        return int(float(str(v).replace(",", "").replace("万", "").replace("%", "")))
    except (TypeError, ValueError):
        return None


def _ca_nonempty(report: Mapping[str, Any]) -> int:
    """Count non-empty core_analysis sections."""
    ca = report.get("core_analysis") or {}
    secs = ca.get("sections", [])
    if not secs:
        # direct-key pattern
        return sum(1 for k, v in ca.items() if k != "sections" and v not in (None, "", [], {}))
    count = 0
    for sec in secs:
        if isinstance(sec, dict):
            body = ca.get(sec.get("key"))
            if body not in (None, "", [], {}):
                if isinstance(body, list):
                    count += 1 if any(isinstance(x, dict) and any(v not in (None, "", "-") for v in x.values()) for x in body) else 0
                else:
                    count += 1
    return count


def _ca_total(report: Mapping[str, Any]) -> int:
    ca = report.get("core_analysis") or {}
    secs = ca.get("sections", [])
    return len(secs) if secs else max(1, len([k for k in ca if k != "sections"]))


def _data_rows(report: Mapping[str, Any]) -> int:
    """Count total data rows/entries across core_analysis."""
    ca = report.get("core_analysis") or {}
    total = 0
    for k, v in ca.items():
        if k == "sections":
            continue
        if isinstance(v, list):
            total += len([x for x in v if isinstance(x, dict)])
        elif isinstance(v, dict):
            total += len(v)
        elif isinstance(v, str) and v.strip():
            total += 1
    return total


def _evidence_strength(report: Mapping[str, Any], dimension: str) -> str:
    """Classify evidence strength for a dimension's report."""
    nm = len(report.get("metrics", []))
    ni = len(report.get("insights", []))
    rows = _data_rows(report)
    # Strong = has substantial primary records + multiple metrics
    if dimension == "risk_health":
        score = _metric_int(report, "风险评分")
        if score is not None:
            return "strong"  # risk score is a direct authoritative assessment
    if dimension == "innovation":
        patent_count = _metric_int(report, "专利总数")
        if patent_count and patent_count > 10:
            return "strong"
    if dimension == "market_activity":
        bid_count = _metric_int(report, "招投标")
        if bid_count and bid_count > 5:
            return "strong"
    if nm >= 4 and rows >= 10:
        return "strong"
    if nm >= 2 or rows >= 3:
        return "medium"
    return "weak"


def _signal_score(report: Mapping[str, Any], dimension: str) -> float:
    """Compute a 0-100 signal quality score for a dimension."""
    nm = len(report.get("metrics", []))
    ni = len(report.get("insights", []))
    rows = _data_rows(report)
    ca_filled = _ca_nonempty(report)
    ca_total = max(1, _ca_total(report))

    # Richness component (0-50)
    richness = min(50, nm * 6 + min(rows, 50) * 0.5 + ni * 4)
    # Coverage component (0-30)
    coverage = (ca_filled / ca_total) * 30
    # Evidence-strength bonus (0-20)
    strength = _evidence_strength(report, dimension)
    strength_bonus = {"strong": 20, "medium": 12, "weak": 5}.get(strength, 5)

    score = richness + coverage + strength_bonus
    return min(100, round(score, 1))


def _dimension_findings(report: Mapping[str, Any], dimension: str) -> Dict[str, Any]:
    """Extract key findings for a dimension."""
    findings: Dict[str, Any] = {"metrics": [], "top_insights": []}
    for m in report.get("metrics", [])[:6]:
        if isinstance(m, dict):
            findings["metrics"].append({"label": m.get("label", ""), "value": m.get("value", ""), "delta": m.get("delta", "")})
    for i in report.get("insights", [])[:3]:
        if isinstance(i, dict):
            findings["top_insights"].append({"feature": i.get("feature", ""), "evidence": i.get("evidence", "")[:120]})
    return findings


def score_dimension(dimension_spec: Mapping[str, Any], reports: Mapping[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Score one fusion dimension from its constituent atomic reports."""
    dim = dimension_spec["dimension"]
    skill_names = dimension_spec["skills"]
    available = [s for s in skill_names if s in reports and reports[s]]

    if not available:
        return {
            "dimension": dim,
            "label": dimension_spec["label"],
            "status": "no_data",
            "signal_score": 0,
            "evidence_strength": "none",
            "coverage": 0,
            "skills_available": [],
            "findings": {},
        }

    # Aggregate signal across constituent skills
    scores = []
    all_findings = []
    for sn in available:
        r = reports[sn]
        sc = _signal_score(r, dim)
        scores.append(sc)
        all_findings.append(_dimension_findings(r, dim))

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    strength = max((_evidence_strength(reports[sn], dim) for sn in available), key=lambda x: {"strong": 3, "medium": 2, "weak": 1, "none": 0}.get(x, 0))
    total_metrics = sum(len(reports[sn].get("metrics", [])) for sn in available)
    total_rows = sum(_data_rows(reports[sn]) for sn in available)

    return {
        "dimension": dim,
        "label": dimension_spec["label"],
        "weight": dimension_spec["weight"],
        "status": "populated",
        "signal_score": avg_score,
        "evidence_strength": strength,
        "coverage": len(available) / len(skill_names),
        "skills_available": available,
        "skills_missing": [s for s in skill_names if s not in available],
        "data_richness": {"metrics": total_metrics, "data_rows": total_rows, "sub_dimensions": len(available)},
        "findings": all_findings,
    }


def compute_composite(dimension_scores: List[Mapping[str, Any]]) -> Dict[str, Any]:
    """Compute the overall composite score and confidence."""
    populated = [d for d in dimension_scores if d.get("status") == "populated"]
    total_dims = len(dimension_scores)

    if not populated:
        return {"composite_score": 0, "confidence": "none", "dimension_coverage": 0, "overall_strength": "none", "assessment": "无可用数据"}

    # Weighted average of signal scores
    total_weight = sum(d.get("weight", 10) for d in populated)
    weighted_score = sum(d["signal_score"] * d.get("weight", 10) for d in populated)
    composite = round(weighted_score / total_weight, 1) if total_weight else 0

    # Dimension coverage
    coverage = len(populated) / total_dims

    # Overall evidence strength
    strong_count = sum(1 for d in populated if d.get("evidence_strength") == "strong")
    medium_count = sum(1 for d in populated if d.get("evidence_strength") == "medium")

    if coverage >= 0.6 and strong_count >= 3:
        confidence = "high"
        strength = "strong"
        assessment = "多维度数据覆盖充分，核心维度证据强度高，画像可信度高。"
    elif coverage >= 0.4 and (strong_count + medium_count) >= 3:
        confidence = "medium"
        strength = "medium"
        assessment = "主要维度数据可用，部分维度数据较薄，画像具备中等可信度。"
    elif coverage >= 0.2:
        confidence = "low"
        strength = "weak"
        assessment = "仅少数维度有数据，画像为局部视角，建议补充更多维度数据。"
    else:
        confidence = "none"
        strength = "weak"
        assessment = "数据严重不足，无法形成有效画像。"

    return {
        "composite_score": composite,
        "confidence": confidence,
        "confidence_label": {"high": "高置信度", "medium": "中置信度", "low": "低置信度", "none": "无数据"}.get(confidence, confidence),
        "dimension_coverage": round(coverage * 100),
        "dimensions_populated": len(populated),
        "dimensions_total": total_dims,
        "overall_strength": strength,
        "strong_dimensions": strong_count,
        "assessment": assessment,
    }


def build_radar_data(dimension_scores: List[Mapping[str, Any]]) -> Dict[str, Any]:
    """Build radar chart data from dimension scores."""
    indicators = []
    values = []
    for d in dimension_scores:
        label = d.get("label", d.get("dimension", ""))
        score = d.get("signal_score", 0) if d.get("status") == "populated" else 0
        indicators.append({"name": label, "max": 100})
        values.append(score)
    return {"indicators": indicators, "series": [{"name": "维度评分", "value": values}]}


def _extract_detail_sections(reports: Mapping[str, Dict[str, Any]], skill_names: Sequence[str]) -> tuple[list, list, list]:
    """Extract real detail data (tables, KV, charts) from atomic reports.

    Returns: (detail_sections, all_metrics, all_insights)
    - detail_sections: list of {key, title, kind, note, columns, chart, data} for rendering
    - all_metrics: collected metrics from these skills
    - all_insights: collected insights from these skills
    """
    detail_sections = []
    all_metrics = []
    all_insights = []

    for sn in skill_names:
        r = reports.get(sn)
        if not r or not isinstance(r, dict):
            continue

        # Collect metrics and insights
        skill_metrics = r.get("metrics", [])
        skill_insights = r.get("insights", [])
        all_metrics.extend(skill_metrics[:8])
        all_insights.extend(skill_insights[:3])

        # Extract core_analysis sections with real data
        ca = r.get("core_analysis", {})
        secs = ca.get("sections", [])
        if secs:
            for sec in secs:
                if not isinstance(sec, dict):
                    continue
                key = sec.get("key")
                body = ca.get(key)
                if body in (None, "", [], {}):
                    continue
                # Only include table/chart/kv sections with real data
                kind = sec.get("kind", "table")
                if kind in ("table", "kv", "line", "bar", "pie", "donut", "multi_line"):
                    rows = body if isinstance(body, list) else ([body] if isinstance(body, dict) else [])
                    rows = [x for x in rows if isinstance(x, dict) and any(v not in (None, "", "-") for v in x.values())] if isinstance(body, list) else rows
                    if rows or (isinstance(body, dict) and body):
                        # Prefix the key to avoid collisions across skills
                        prefixed_key = f"{sn}__{key}"
                        detail_sections.append({
                            **sec,
                            "key": prefixed_key,
                            "title": f"[{sn.replace('-report','')}] {sec.get('title', key)}",
                            "_data_key": key,  # actual key in core_analysis
                            "_skill": sn,
                        })
        else:
            # Direct-key pattern (e.g. enterprise-report)
            for k, v in ca.items():
                if k == "sections" or v in (None, "", [], {}):
                    continue
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    rows = [x for x in v if isinstance(x, dict) and any(val not in (None, "", "-") for val in x.values())]
                    if rows:
                        prefixed_key = f"{sn}__{k}"
                        cols = [(ck, ck) for ck in rows[0].keys()]
                        detail_sections.append({"key": prefixed_key, "title": f"[{sn.replace('-report','')}] {k}", "kind": "table", "columns": cols, "_data_key": k, "_skill": sn})
                elif isinstance(v, dict) and v:
                    prefixed_key = f"{sn}__{k}"
                    detail_sections.append({"key": prefixed_key, "title": f"[{sn.replace('-report','')}] {k}", "kind": "kv", "_data_key": k, "_skill": sn})
                elif isinstance(v, str) and v.strip() and len(v.strip()) > 10:
                    prefixed_key = f"{sn}__{k}"
                    detail_sections.append({"key": prefixed_key, "title": f"[{sn.replace('-report','')}] {k}", "kind": "text", "_data_key": k, "_skill": sn})

    return detail_sections, all_metrics, all_insights


def build_fusion_payload(enterprise: str, reports: Mapping[str, Dict[str, Any]], *, source_mode: str = "local", scenario: str = "full") -> Dict[str, Any]:
    """Build the complete fusion report payload with real detail data, filtered by scenario."""
    # Resolve scenario preset
    preset = SCENARIO_PRESETS.get(scenario, SCENARIO_PRESETS["full"])
    active_dims = preset.get("dimensions")
    weight_overrides = preset.get("weight_overrides", {})

    # Filter dimensions by scenario (or use all)
    matrix = DIMENSION_MATRIX if active_dims is None else [d for d in DIMENSION_MATRIX if d["dimension"] in active_dims]
    matrix = [{**d, "weight": weight_overrides.get(d["dimension"], d["weight"])} for d in matrix]

    # Score each dimension
    dim_scores = [score_dimension(ds, reports) for ds in matrix]
    composite = compute_composite(dim_scores)
    radar = build_radar_data(dim_scores)

    # Extract enterprise base info
    base_info = {}
    if reports.get("enterprise-report"):
        er = reports["enterprise-report"]
        for m in er.get("metrics", []):
            if isinstance(m, dict):
                base_info[m.get("label", "")] = m.get("value", "")
        ca = er.get("core_analysis", {})
        if isinstance(ca.get("enterprise_base"), list):
            for row in ca["enterprise_base"]:
                if isinstance(row, dict):
                    base_info[row.get("字段", "")] = row.get("内容", "")

    # Extract REAL DETAIL DATA from all relevant atomic reports
    relevant_skills = sorted(set(s for d in matrix for s in d["skills"]))
    detail_sections, detail_metrics, detail_insights = _extract_detail_sections(reports, relevant_skills)

    # Build flat core_analysis data dict for renderer
    core_data = {}
    for sec in detail_sections:
        dk = sec["_data_key"]
        sn = sec["_skill"]
        r = reports.get(sn, {})
        ca = r.get("core_analysis", {})
        core_data[sec["key"]] = ca.get(dk)

    # Build quality report
    quality = {
        "dimensions_total": len(dim_scores),
        "dimensions_populated": sum(1 for d in dim_scores if d.get("status") == "populated"),
        "dimensions_empty": sum(1 for d in dim_scores if d.get("status") == "no_data"),
        "coverage_pct": round(sum(1 for d in dim_scores if d.get("status") == "populated") / len(dim_scores) * 100),
        "empty_dimensions": [d["label"] for d in dim_scores if d.get("status") == "no_data"],
        "detail_sections": len(detail_sections),
        "detail_data_rows": sum(len(v) for v in core_data.values() if isinstance(v, list)),
    }

    # Build abstract
    name = enterprise or base_info.get("企业名称", "目标企业")
    title_suffix = preset.get("title_suffix", "企业综合画像报告")
    scenario_label = preset.get("label", "全维度综合画像")
    abstract_parts = [f"本报告以\u201c{name}\u201d为分析对象，基于\u201c{scenario_label}\u201d场景，聚合 {quality['dimensions_populated']}/{quality['dimensions_total']} 个维度、{len(relevant_skills)} 个数据源的多源数据，"]
    abstract_parts.append(f"综合评分 {composite['composite_score']} 分（{composite['confidence_label']}），维度覆盖率 {composite['dimension_coverage']}%。")
    abstract_parts.append(f"报告包含 {len(detail_sections)} 个明细章节、{quality['detail_data_rows']} 条数据记录。")
    abstract_parts.append(composite["assessment"])
    abstract = "".join(abstract_parts)

    # Build section specs for renderer (radar + dimension table + all detail sections)
    render_sections = [
        {"key": "radar", "title": f"{scenario_label}雷达图", "kind": "radar", "note": f"本场景 {len(matrix)} 维度信号评分（0-100），覆盖面越大综合实力越强", "chart": {}},
        {"key": "dimension_detail", "title": "各维度评分总览", "kind": "table", "note": "按维度展开评分、证据强度、覆盖度与关键发现", "columns": [["维度", "维度"], ["评分", "评分"], ["证据强度", "证据强度"], ["覆盖度", "覆盖度"], ["关键发现", "关键发现"]]},
    ]
    # Add detail sections (strip internal keys)
    for sec in detail_sections:
        clean_sec = {k: v for k, v in sec.items() if not k.startswith("_")}
        render_sections.append(clean_sec)

    # Build enriched metrics (composite + key dimension metrics)
    enriched_metrics = [
        {"label": "综合评分", "value": str(composite["composite_score"]), "hint": "加权多维度评分", "delta": composite["confidence_label"]},
        {"label": "维度覆盖", "value": f"{composite['dimension_coverage']}%", "hint": f"{composite['dimensions_populated']}/{composite['dimensions_total']} 维度有数据"},
        {"label": "明细章节", "value": str(len(detail_sections)), "hint": f"{quality['detail_data_rows']} 条数据记录"},
        {"label": "数据来源", "value": str(len([r for r in reports.values() if r])), "hint": "已聚合的原子报告数"},
    ]
    # Add top dimension-specific metrics
    for dm in dim_scores:
        if dm.get("status") == "populated":
            for f in dm.get("findings", []):
                if isinstance(f, dict):
                    for m in f.get("metrics", [])[:2]:
                        if isinstance(m, dict) and len(enriched_metrics) < 16:
                            enriched_metrics.append(m)

    # Build enriched insights (dimension scores + atomic insights)
    enriched_insights = []
    for d in dim_scores:
        if d.get("status") == "populated":
            enriched_insights.append({
                "feature": f"{d['label']}（评分 {d['signal_score']}）",
                "evidence": f"证据强度\u201c{ {'strong': '强', 'medium': '中', 'weak': '弱'}.get(d.get('evidence_strength', ''), '-') }\u201d，覆盖度 {round(d.get('coverage', 0) * 100)}%。",
                "interpretation": d["label"] + "维度" + ("数据充分" if d.get("signal_score", 0) >= 50 else "数据较薄" if d.get("signal_score", 0) >= 20 else "数据不足"),
            })
    # Add real insights from atomic reports
    for ins in detail_insights[:8]:
        if isinstance(ins, dict) and len(enriched_insights) < 16:
            enriched_insights.append(ins)

    return {
        "report_type": f"{scenario}_report",
        "title": f"{name} {title_suffix}",
        "banner": scenario_label,
        "subject": {"enterprise": name, "base_info": base_info},
        "abstract": abstract,
        "summary": abstract,
        "executive_summary": [composite["assessment"]],
        "composite": composite,
        "dimension_scores": dim_scores,
        "radar_data": radar,
        "quality_report": quality,
        "source_mode": source_mode,
        "scenario": scenario,
        "scenario_label": scenario_label,
        "scenario_description": preset.get("description", ""),
        "data_sources": {
            "atomic_skills_used": relevant_skills,
            "total_atomic_reports": len([r for r in reports.values() if r]),
            "detail_sections": len(detail_sections),
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        },
        "metrics": enriched_metrics,
        "core_analysis": {
            "sections": render_sections,
            "radar": radar,
            "dimension_detail": [
                {
                    "维度": d.get("label", ""),
                    "评分": str(d.get("signal_score", 0)),
                    "证据强度": {"strong": "强", "medium": "中", "weak": "弱", "none": "无"}.get(d.get("evidence_strength", ""), "-"),
                    "覆盖度": f"{round(d.get('coverage', 0) * 100)}%" if d.get("status") == "populated" else "无数据",
                    "关键发现": "; ".join(f.get("top_insights", [{}])[0].get("evidence", "")[:40] for f in d.get("findings", []) if isinstance(f, dict) and f.get("top_insights"))[:80] if d.get("status") == "populated" else "-",
                }
                for d in dim_scores
            ],
            **core_data,  # all detail section data keyed by prefixed key
        },
        "representative_records": [],
        "insights": enriched_insights,
        "caliber": {
            "match_target": name,
            "match_type": f"{scenario_label}（融合 {len(relevant_skills)} 个原子 skill）",
            "data_scope": f"覆盖 {quality['dimensions_populated']}/{quality['dimensions_total']} 个维度，{len(detail_sections)} 个明细章节，{quality['detail_data_rows']} 条记录",
            "products": [f"{s} 的 MCP 数据" for s in relevant_skills],
            "limit": "综合评分基于数据丰富度与证据强度加权计算；明细数据来自各原子 skill 的真实查询结果。",
        },
    }
