#!/usr/bin/env python3
"""Shared helpers for the enterprise-fusion-skill."""
from __future__ import annotations

import json
from typing import Any

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
