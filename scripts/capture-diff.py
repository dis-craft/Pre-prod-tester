#!/usr/bin/env python3
"""Capture the exact files changed by a push as structured JSON.

Phase 1 only captures changes. It deliberately does not execute repository
code or perform vulnerability detection.
"""
from __future__ import annotations
import json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCANS = DATA / "scans"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()

def changed_files(before: str, after: str) -> list[dict]:
    base = before if before and set(before) != {"0"} else EMPTY_TREE
    common = ["git", "diff", "--no-ext-diff", base, after, "--",
              ".", ":(exclude)data/**", ":(exclude).git/**"]

    statuses = subprocess.check_output(
        common[:3] + ["--name-status"] + common[3:],
        cwd=ROOT, text=True
    )
    numstats = subprocess.check_output(
        common[:3] + ["--numstat"] + common[3:],
        cwd=ROOT, text=True
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
                ["git", "diff", "--no-ext-diff", "--unified=80",
                 base, after, "--", path],
                cwd=ROOT, text=True, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            patch = ""
        result.append({
            "path": path,
            "status": status,
            "language": Path(path).suffix.lstrip(".") or "unknown",
            "changes": {"additions": add, "deletions": delete, "total": add + delete},
            "diff": patch,
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
            "default_branch": "main",
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

    index_path = DATA / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        index = {"schema_version": "1.0", "scans": []}

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

if __name__ == "__main__":
    main()
