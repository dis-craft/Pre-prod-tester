#!/usr/bin/env python3
"""Attach normalized security findings to the published Pre-Prod scan payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", required=True)
    parser.add_argument("--findings", required=True)
    args = parser.parse_args()

    scan_path = Path(args.scan)
    findings_path = Path(args.findings)

    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    findings_report = json.loads(findings_path.read_text(encoding="utf-8"))

    findings = findings_report.get("findings", [])
    metadata = findings_report.get("scan_metadata", {})

    scan["security_engine"] = {
        "status": "FAILED" if any(
            str(f.get("severity", "")).upper() in {"HIGH", "CRITICAL"}
            for f in findings
        ) else "PASSED",
        "scanner": "Pre-Prod-Orchestrator/rule_engine",
        "findings": findings,
        "scan_metadata": metadata,
    }

    scan_path.write_text(json.dumps(scan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
