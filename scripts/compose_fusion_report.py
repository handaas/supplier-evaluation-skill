#!/usr/bin/env python3
"""Compose a supplier-evaluation report.

Default mode (direct-mcp): connect to 6 MCP servers (enterprise / risk /
operation / channel / factory / recruitment), pull raw data, run cross-domain
analysis, and produce a rich report with cross-dimensional insights + specialty
score matrix + structured verdict. Use ``--dry-run`` to read cached reports_探迹/
JSONs without contacting MCP.

Legacy modes (``--reports-dir`` / ``--skills-dir`` / ``--no-direct-mcp``):
aggregate pre-existing atomic-skill reports via fusion_engine.

Usage::

  # default: direct multi-MCP (or dry-run from cached reports)
  python compose_fusion_report.py --enterprise "广州探迹科技有限公司" \\
    --dry-run --output output/供应商.json --report-output output/供应商.html

  # real run (needs MCP connection configured)
  python compose_fusion_report.py --enterprise "广州探迹科技有限公司" \\
    --output output/供应商.json --report-output output/供应商.html

  # legacy: aggregate pre-existing atomic reports
  python compose_fusion_report.py --enterprise "广州探迹科技有限公司" \\
    --reports-dir ../../reports_探迹 --output output/供应商.json --report-output output/供应商.html
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Any, Dict

from common import json_dumps, print_json
from render_report import render_html, render_markdown, html_to_pdf

SKILLS_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _emit(payload: Dict[str, Any], args: argparse.Namespace) -> None:
    """Write JSON + optional HTML + Markdown output."""
    if args.output:
        out = pathlib.Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_dumps(payload, pretty=True), encoding="utf-8")
        print_json({"ok": True, "json": str(out), "dry_run": args.dry_run})
    else:
        print_json(payload)
    if args.report_output:
        base = pathlib.Path(args.report_output).expanduser()
        base.parent.mkdir(parents=True, exist_ok=True)
        html_path = base.with_suffix(".html") if base.suffix.lower() not in (".html", ".htm") else base
        md_path = html_path.with_suffix(".md")
        html_path.write_text(render_html(payload), encoding="utf-8")
        md_path.write_text(render_markdown(payload), encoding="utf-8")
        pdf_path = None
        if args.pdf_output:
            pdf_path = pathlib.Path(args.pdf_output).expanduser()
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            html_to_pdf(render_html(payload), str(pdf_path))
        print_json({"ok": True, "html": str(html_path), "markdown": str(md_path), "pdf": str(pdf_path) if pdf_path else None, "dry_run": args.dry_run})


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose a supplier-evaluation report.")
    parser.add_argument("--enterprise", required=True, help="企业全称或关键词（关键词自动模糊补全）")
    parser.add_argument("--keyword-type", default="name", help="主体类型：name/nameId/regNumber/socialCreditCode")
    parser.add_argument("--dry-run", action="store_true", help="不调真实 MCP，读缓存报告做交叉分析")
    parser.add_argument("--no-direct-mcp", action="store_true", help="禁用多 MCP 直连，改用旧融合引擎聚合原子报告")
    parser.add_argument("--reports-dir", help="[旧模式] 读取已有原子报告 JSON 的目录")
    parser.add_argument("--skills-dir", help="[旧模式] 运行各原子 skill 生成报告")
    parser.add_argument("--output-dir", default="output", help="临时报告输出目录（旧模式）")
    parser.add_argument("--output", help="输出 JSON 路径")
    parser.add_argument("--report-output", help="同时输出 HTML + Markdown")
    parser.add_argument("--pdf-output", help="额外输出 PDF 报告（.pdf）；需要 Playwright + Chromium")
    args = parser.parse_args()

    # Default: direct multi-MCP mode (unless legacy flags explicitly request old engine)
    use_direct = not (args.no_direct_mcp or args.reports_dir or args.skills_dir)
    if use_direct:
        print(f"模式: 直连多 MCP 交叉分析（{'dry-run 缓存' if args.dry_run else '真实查询'}）", file=sys.stderr)
        from compose_direct import build_direct_payload
        payload = build_direct_payload(args.enterprise, args.keyword_type, dry_run=args.dry_run, skills_root=str(SKILLS_ROOT))
        _emit(payload, args)
        return

    # Legacy: fusion_engine aggregation
    print("模式: 旧融合引擎（聚合原子报告）", file=sys.stderr)
    from fusion_engine import DIMENSION_MATRIX, build_fusion_payload, load_existing_report, run_atomic_skill

    all_atomic = sorted(set(s for d in DIMENSION_MATRIX for s in d["skills"]))

    def collect_local(reports_dir: str) -> Dict[str, Dict[str, Any]]:
        reports: Dict[str, Dict[str, Any]] = {}
        for skill in all_atomic:
            r = load_existing_report(skill, reports_dir)
            if r:
                reports[skill] = r
        return reports

    def collect_fresh(skills_dir: str, output_dir: str) -> Dict[str, Dict[str, Any]]:
        reports: Dict[str, Dict[str, Any]] = {}
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        for skill in all_atomic:
            r = run_atomic_skill(skill, args.enterprise, skills_dir, output_dir=output_dir, dry_run=args.dry_run)
            if r:
                reports[skill] = r
        return reports

    if not args.reports_dir and not args.skills_dir:
        default_reports = SKILLS_ROOT / "reports_探迹"
        if default_reports.exists():
            args.reports_dir = str(default_reports)
        else:
            args.skills_dir = str(SKILLS_ROOT)

    if args.reports_dir:
        reports = collect_local(args.reports_dir)
        source_mode = "existing_reports"
    else:
        reports = collect_fresh(args.skills_dir, args.output_dir)
        source_mode = "local_atomic"

    if not reports:
        print("错误: 未获取到任何原子报告数据", file=sys.stderr)
        raise SystemExit(1)

    print(f"已聚合 {len(reports)}/{len(all_atomic)} 个原子报告 (场景: supplier)", file=sys.stderr)
    payload = build_fusion_payload(args.enterprise, reports, source_mode=source_mode, scenario="supplier")
    _emit(payload, args)


if __name__ == "__main__":
    main()
