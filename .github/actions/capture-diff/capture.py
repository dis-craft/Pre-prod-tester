#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())).resolve()
OUTPUT = ROOT / os.environ.get("PREPROD_OUTPUT", ".preprod/scan.json")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: (.*))?$")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def parse_patch(patch: str):
    hunks, added, removed = [], [], []
    current = None
    old_line = new_line = 0

    for raw in patch.splitlines():
        match = HUNK_RE.match(raw)
        if match:
            old_line, new_line = int(match.group(1)), int(match.group(3))
            current = {
                "header": raw,
                "old_start": old_line,
                "old_count": int(match.group(2) or "1"),
                "new_start": new_line,
                "new_count": int(match.group(4) or "1"),
                "lines": [],
            }
            hunks.append(current)
            continue

        if current is None or raw == "":
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


def capture(before: str, after: str):
    base = before if before and set(before) != {"0"} else "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

    statuses = subprocess.check_output(
        ["git", "diff", "--no-ext-diff", "--name-status", base, after, "--", "."],
        cwd=ROOT, text=True
    )
    numstats = subprocess.check_output(
        ["git", "diff", "--no-ext-diff", "--numstat", base, after, "--", "."],
        cwd=ROOT, text=True
    )

    stats = {}
    for row in numstats.splitlines():
        parts = row.split("\t")
        if len(parts) >= 3:
            stats[parts[-1]] = (
                0 if parts[0] == "-" else int(parts[0]),
                0 if parts[1] == "-" else int(parts[1]),
            )

    files = []
    for row in statuses.splitlines():
        parts = row.split("\t")
        status, path = parts[0], parts[-1]
        additions, deletions = stats.get(path, (0, 0))

        patch = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--unified=80", base, after, "--", path],
            cwd=ROOT, text=True, capture_output=True
        ).stdout

        hunks, added_lines, removed_lines = parse_patch(patch)

        files.append({
            "path": path,
            "status": status,
            "language": Path(path).suffix.lstrip(".") or "unknown",
            "changes": {
                "additions": additions,
                "deletions": deletions,
                "total": additions + deletions,
            },
            "diff": patch,
            "hunks": hunks,
            "added_lines": added_lines,
            "removed_lines": removed_lines,
        })

    return files


def main():
    before = os.environ.get("PREPROD_BEFORE", "")
    after = os.environ.get("PREPROD_AFTER") or git("rev-parse", "HEAD")
    repo = os.environ.get("PREPROD_REPOSITORY", "")
    server = os.environ.get("PREPROD_SERVER", "https://github.com")
    branch = os.environ.get("PREPROD_REF", "")
    run_id = os.environ.get("PREPROD_RUN_ID", "")

    files = capture(before, after)
    additions = sum(f["changes"]["additions"] for f in files)
    deletions = sum(f["changes"]["deletions"] for f in files)

    payload = {
        "schema_version": "1.0",
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
            "default_branch": branch,
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
            "legend": {"added": "+", "removed": "-", "context": " "},
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

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Captured {len(files)} files (+{additions}/-{deletions})")
    print(f"JSON: {OUTPUT}")


if __name__ == "__main__":
    main()
