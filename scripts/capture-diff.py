#!/usr/bin/env python3
"""Capture a push diff as structured JSON for the Phase 1 static report.

This script only reads Git metadata/diffs. It never executes repository code.
Generated data is written to the runner workspace and published as a Pages
artifact. The workflow persists the generated data separately.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCANS = DATA / "scans"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: (.*))?$")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, errors="replace", stderr=subprocess.DEVNULL
    ).strip()


def parse_patch(patch: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Return hunks plus normalized added/removed/context line records."""
    hunks: list[dict] = []
    added: list[dict] = []
    removed: list[dict] = []
    current = None
    old_line = new_line = 0

    for raw in patch.splitlines():
        match = HUNK_RE.match(raw)
        if match:
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_start = int(match.group(3))
            new_count = int(match.group(4) or "1")
            current = {
                "header": raw,
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "lines": [],
            }
            hunks.append(current)
            old_line, new_line = old_start, new_start
            continue

        # Ignore the file headers and binary-file notices outside hunks.
        if current is None or not raw:
            continue

        marker = raw[0]
        content = raw[1:] if marker in ("+", "-", " ") else raw

        if marker == "+":
            item = {"type": "added", "new_line": new_line, "content": content}
            current["lines"].append(item)
            added.append(item.copy())
            new_line += 1
        elif marker == "-":
            item = {"type": "removed", "old_line": old_line, "content": content}
            current["lines"].append(item)
            removed.append(item.copy())
            old_line += 1
        elif marker == " ":
            current["lines"].append({
                "type": "context",
                "old_line": old_line,
                "new_line": new_line,
                "content": content,
            })
            old_line += 1
            new_line += 1

    return hunks, added, removed


def changed_files(before: str, after: str) -> list[dict]:
    base = before if before and set(before) != {"0"} else EMPTY_TREE
    pathspec = [".", ":(exclude)data/**", ":(exclude).git/**"]

    statuses = subprocess.check_output(
        ["git", "diff", "--no-ext-diff", "--text", "--name-status", base, after, "--", *pathspec],
        cwd=ROOT, text=True, errors="replace",
    )
    numstats = subprocess.check_output(
        ["git", "diff", "--no-ext-diff", "--text", "--numstat", base, after, "--", *pathspec],
        cwd=ROOT, text=True, errors="replace",
    )

    stats = {}
    for line in numstats.splitlines():
        p = line.split("\t")
        if len(p) >= 3:
            stats[p[-1]] = (
                0 if p[0] == "-" else int(p[0]),
                0 if p[1] == "-" else int(p[1]),
            )

    result = []
    for line in statuses.splitlines():
        p = line.split("\t")
        status, path = p[0], p[-1]
        add, delete = stats.get(path, (0, 0))

        try:
            patch = subprocess.check_output(
                ["git", "diff", "--no-ext-diff", "--text", "--unified=80",
                 base, after, "--", path],
                cwd=ROOT, text=True, errors="replace", stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            patch = ""

        hunks, added_lines, removed_lines = parse_patch(patch)

        result.append({
            "path": path,
            "status": status,
            "language": Path(path).suffix.lstrip(".") or "unknown",
            "changes": {
                "additions": add,
                "deletions": delete,
                "total": add + delete,
            },
            "diff": patch,
            "hunks": hunks,
            "added_lines": added_lines,
            "removed_lines": removed_lines,
        })

    return result


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    SCANS.mkdir(parents=True, exist_ok=True)

    event = {}
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if event_path and Path(event_path).exists():
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))

    before = os.environ.get("GITHUB_EVENT_BEFORE") or event.get("before") or ""
    after = os.environ.get("GITHUB_SHA") or event.get("after") or git("rev-parse", "HEAD")
    files = changed_files(before, after)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    additions = sum(x["changes"]["additions"] for x in files)
    deletions = sum(x["changes"]["deletions"] for x in files)

    payload = {
        "schema_version": "1.1",
        "scan": {
            "id": f"scn_{after[:12]}",
            "trigger": "push",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "workflow_run_id": run_id,
            "workflow_url": f"{server}/{repo}/actions/runs/{run_id}",
        },
        "repository": {
            "full_name": repo,
            "url": f"{server}/{repo}",
            "default_branch": "main",
        },
        "comparison": {
            "base_commit": before,
            "target_commit": after,
            "range": f"{before}..{after}" if before else after,
            "method": "git diff two-commit comparison",
        },
        "commit": {
            "before": before,
            "after": after,
            "branch": branch,
            "message": git("show", "-s", "--format=%s", after),
            "author": {
                "name": git("show", "-s", "--format=%an", after),
                "email": git("show", "-s", "--format=%ae", after),
            },
            "committed_at": git("show", "-s", "--format=%cI", after),
        },
        "change_summary": {
            "files_changed": len(files),
            "additions": additions,
            "deletions": deletions,
            "net_lines": additions - deletions,
        },
        "changes": {
            "format": "github-style-unified-diff",
            "legend": {
                "added": "+",
                "removed": "-",
                "context": " ",
            },
            "files": [
                {
                    "path": f["path"],
                    "status": f["status"],
                    "additions": f["changes"]["additions"],
                    "deletions": f["changes"]["deletions"],
                    "added_lines": f["added_lines"],
                    "removed_lines": f["removed_lines"],
                    "hunks": f["hunks"],
                }
                for f in files
            ],
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

    (SCANS / f"{after}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (DATA / "latest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Keep any existing history that is present in the checked-out repository.
    index_path = DATA / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        index = {"schema_version": "1.1", "scans": []}

    index["schema_version"] = "1.1"
    index["scans"] = [x for x in index.get("scans", []) if x.get("commit") != after]
    index["scans"].insert(0, {
        "scan_id": payload["scan"]["id"],
        "commit": after,
        "parent": before,
        "branch": branch,
        "message": payload["commit"]["message"],
        "captured_at": payload["scan"]["captured_at"],
        "files_changed": len(files),
        "additions": additions,
        "deletions": deletions,
        "url": f"scans/{after}.json",
    })
    index["scans"] = index["scans"][:100]
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    print(f"Captured {len(files)} files (+{additions}/-{deletions})")
    print(f"Comparison: {before}..{after}")


if __name__ == "__main__":
    main()
