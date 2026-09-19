#!/usr/bin/env python3
"""Capture a push as a structured, machine-readable change record.

This script intentionally does not execute repository/application code.
It only reads Git metadata and textual diffs.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
SCANS_DIR = DATA_DIR / "scans"

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def run(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def git_or_default(default: str, *args: str) -> str:
    try:
        value = run(*args)
        return value if value else default
    except subprocess.CalledProcessError:
        return default


def safe_diff(before: str, after: str) -> list[str]:
    if not before or set(before) == {"0"}:
        before = EMPTY_TREE
    # Generated scan data is not application code and must not pollute the next scan.
    return [
        "git",
        "diff",
        "--no-ext-diff",
        "--unified=80",
        before,
        after,
        "--",
        ".",
        ":(exclude)data/**",
        ":(exclude).git/**",
    ]


def parse_changed_files(before: str, after: str) -> list[dict]:
    if not before or set(before) == {"0"}:
        before = EMPTY_TREE

    raw = subprocess.check_output(
        [
            "git",
            "diff",
            "--no-ext-diff",
            "--numstat",
            "--name-status",
            before,
            after,
            "--",
            ".",
            ":(exclude)data/**",
            ":(exclude).git/**",
        ],
        cwd=REPO_ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
    )

    files: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue

        # --numstat --name-status emits:
        # additions<TAB>deletions<TAB>path<TAB>status<TAB>path
        # depending on Git version/options. Parse conservatively.
        parts = line.split("\t")
        additions = deletions = 0
        status = "modified"
        path = parts[-1]

        for part in parts:
            if part.isdigit() and additions == 0:
                additions = int(part)
            elif part.isdigit() and deletions == 0:
                deletions = int(part)

        for part in parts:
            if part.startswith(("A", "M", "D", "R", "C", "T", "U")):
                status = part
                break

        if status.startswith("R") and len(parts) >= 2:
            path = parts[-1]

        # Ask Git for the exact per-file diff. This avoids trying to reconstruct
        # patches from line counts.
        try:
            diff = subprocess.check_output(
                [
                    "git",
                    "diff",
                    "--no-ext-diff",
                    "--unified=80",
                    before,
                    after,
                    "--",
                    path,
                ],
                cwd=REPO_ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            diff = ""

        files.append(
            {
                "path": path,
                "status": status,
                "language": Path(path).suffix.lstrip(".") or "unknown",
                "changes": {
                    "additions": additions,
                    "deletions": deletions,
                    "total": additions + deletions,
                },
                "diff": diff,
            }
        )

    return files


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCANS_DIR.mkdir(parents=True, exist_ok=True)

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    event = {}
    if event_path and Path(event_path).exists():
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))

    before = os.environ.get("GITHUB_EVENT_BEFORE") or event.get("before") or ""
    after = os.environ.get("GITHUB_SHA") or event.get("after") or run("rev-parse", "HEAD")

    if not before or set(before) == {"0"}:
        before_for_git = EMPTY_TREE
    else:
        before_for_git = before

    files = parse_changed_files(before_for_git, after)

    additions = sum(f["changes"]["additions"] for f in files)
    deletions = sum(f["changes"]["deletions"] for f in files)

    message = git_or_default("", "show", "-s", "--format=%s", after)
    author_name = git_or_default("", "show", "-s", "--format=%an", after)
    author_email = git_or_default("", "show", "-s", "--format=%ae", after)
    committed_at = git_or_default("", "show", "-s", "--format=%cI", after)

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    ref = os.environ.get("GITHUB_REF_NAME", "main")

    payload = {
        "schema_version": "1.0",
        "scan": {
            "id": f"scn_{after[:12]}",
            "trigger": "push",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_url": (
                f"{server}/{repository}/actions/runs/"
                f"{os.environ.get('GITHUB_RUN_ID', '')}"
            ),
        },
        "repository": {
            "full_name": repository,
            "url": f"{server}/{repository}",
            "default_branch": "main",
        },
        "commit": {
            "before": before,
            "after": after,
            "branch": ref,
            "message": message,
            "author": {
                "name": author_name,
                "email": author_email,
            },
            "committed_at": committed_at,
        },
        "change_summary": {
            "files_changed": len(files),
            "additions": additions,
            "deletions": deletions,
        },
        "security_context": {
            "detection_enabled": False,
            "secrets_scan": False,
            "sast_scan": False,
            "dependency_scan": False,
            "llm_analysis": False,
        },
        "files": files,
    }

    scan_path = SCANS_DIR / f"{after}.json"
    scan_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # latest.json is the stable machine endpoint.
    (DATA_DIR / "latest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    index_path = DATA_DIR / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        index = {"schema_version": "1.0", "scans": []}

    scans = [s for s in index.get("scans", []) if s.get("commit") != after]
    scans.insert(
        0,
        {
            "scan_id": payload["scan"]["id"],
            "commit": after,
            "parent": before,
            "branch": ref,
            "message": message,
            "captured_at": payload["scan"]["captured_at"],
            "files_changed": len(files),
            "additions": additions,
            "deletions": deletions,
            "url": f"scans/{after}.json",
        },
    )
    index["scans"] = scans[:100]

    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Captured {len(files)} changed files")
    print(f"Additions: {additions}")
    print(f"Deletions: {deletions}")
    print(f"Scan: {scan_path}")


if __name__ == "__main__":
    main()
