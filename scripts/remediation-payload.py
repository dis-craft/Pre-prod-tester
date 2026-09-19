#!/usr/bin/env python3
"""Build a minimal remediation request for Pre-Prod Orchestrator.

Reads a scanner report/finding JSON and emits a stable payload containing the
repository, finding, and the commit to remediate. Patch generation remains in
the orchestrator; this bridge does not modify source code.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def load_json(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Unable to read JSON {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Scanner findings/report JSON")
    parser.add_argument("--output", default=".preprod/remediation-request.json")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--ref", default=os.environ.get("GITHUB_REF_NAME", ""))
    parser.add_argument("--pull-request", default=os.environ.get("PR_NUMBER", ""))
    parser.add_argument("--generate", action="store_true", help="Request remediation generation")
    args = parser.parse_args()

    source = load_json(args.input)
    findings = source.get("findings", [])
    if not findings and isinstance(source.get("result"), dict):
        findings = source["result"].get("findings", [])
    if not isinstance(findings, list):
        raise SystemExit("Input does not contain a findings list")

    payload = {
        "repository": args.repository,
        "commit_sha": args.commit,
        "ref": args.ref,
        "pull_request": args.pull_request or None,
        "generate_remediation": bool(args.generate),
        "findings": findings,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
