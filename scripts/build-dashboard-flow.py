#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def api(path: str):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def find_run(runs, names, sha):
    matches = [
        r for r in runs.get("workflow_runs", [])
        if r.get("name") in names and r.get("head_sha") == sha
    ]
    matches.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return matches[0] if matches else None


def jobs_for(run):
    if not run:
        return []
    return api(f"/actions/runs/{run['id']}/jobs?per_page=100").get("jobs", [])


def step_status(jobs, step_name):
    for job in jobs:
        for step in job.get("steps", []):
            if step.get("name") != step_name:
                continue
            status = step.get("status")
            conclusion = step.get("conclusion")
            if status in {"queued", "in_progress"}:
                return "running", f"{step_name} is running.", job.get("html_url")
            if conclusion == "success":
                return "pass", f"{step_name} completed successfully.", job.get("html_url")
            if conclusion in {"cancelled", "timed_out", "action_required"}:
                return "error", f"{step_name} ended as {conclusion}.", job.get("html_url")
            if conclusion:
                return "fail", f"{step_name} ended as {conclusion}.", job.get("html_url")
    return "waiting", f"Waiting for {step_name}.", None


def run_status(run):
    if not run:
        return "waiting"
    if run.get("status") in {"queued", "requested", "waiting", "in_progress"}:
        return "running"
    if run.get("conclusion") == "success":
        return "pass"
    if run.get("conclusion") in {"cancelled", "timed_out", "action_required"}:
        return "error"
    return "fail"


def event_sha():
    name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    payload = {}
    if event_path and Path(event_path).exists():
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    if name == "workflow_run":
        return payload.get("workflow_run", {}).get("head_sha") or os.environ["GITHUB_SHA"]
    if name == "pull_request":
        return payload.get("pull_request", {}).get("head", {}).get("sha") or os.environ["GITHUB_SHA"]
    return os.environ["GITHUB_SHA"]


def load_canonical_scan(sha: str):
    candidates = [DATA / "latest.json", DATA / "scans" / f"{sha}.json"]
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        if payload.get("commit", {}).get("after") == sha:
            return payload
    return None


sha = event_sha()
commit = api(f"/commits/{sha}")
runs = api("/actions/runs?per_page=100&sort=created&direction=desc")
prs = api("/pulls?state=all&per_page=100&sort=updated&direction=desc")

capture = find_run(runs, {"Capture Changes and Publish"}, sha)
ai = find_run(runs, {"AI Security Remediation"}, sha)

capture_jobs = jobs_for(capture)
ai_jobs = jobs_for(ai)

scan = load_canonical_scan(sha)
scan_url = (scan or {}).get("scan", {}).get("workflow_url") or (capture or {}).get("html_url")

# Stage 2 and 3 are NOT inferred from generic workflow-step names.
# The canonical Capture workflow already produced the diff and security results.
# This flow only reads those persisted results and reports their state.
if scan:
    summary = scan.get("change_summary", {})
    capture_diff = (
        "pass",
        f"Canonical diff captured: {summary.get('files_changed', 0)} file(s), "
        f"+{summary.get('additions', 0)}/-{summary.get('deletions', 0)}.",
        scan_url,
    )
else:
    state = run_status(capture)
    if state == "running":
        capture_diff = ("running", "Waiting for the canonical capture workflow to finish.", (capture or {}).get("html_url"))
    elif capture and state in {"fail", "error"}:
        capture_diff = ("fail", "Canonical capture workflow failed; no trusted diff is available.", (capture or {}).get("html_url"))
    else:
        capture_diff = ("waiting", "Waiting for canonical capture data.", None)

security_engine = (scan or {}).get("security_engine") or {}
findings = security_engine.get("findings") or []
crit = sum(1 for f in findings if str(f.get("severity", "")).upper() == "CRITICAL")
high = sum(1 for f in findings if str(f.get("severity", "")).upper() == "HIGH")

if scan and isinstance(security_engine, dict) and security_engine.get("scan_metadata") is not None:
    if findings:
        security_detail = f"Security scan completed; {len(findings)} finding(s): {crit} critical, {high} high. Merge remains blocked until remediation is verified."
    else:
        security_detail = "Security scan completed with no blocking findings."
    security = ("pass", security_detail, scan_url)
elif capture_diff[0] == "running":
    security = ("waiting", "Waiting for the canonical security scan results.", (capture or {}).get("html_url"))
elif capture and run_status(capture) in {"fail", "error"}:
    security = ("fail", "Capture/security workflow failed before canonical scan results were published.", (capture or {}).get("html_url"))
else:
    security = ("waiting", "Waiting for canonical security scan results.", None)

ai_step = step_status(ai_jobs, "Run scanner and AI remediation")
if not findings:
    ai_step = ("pass", "No blocking findings were detected; AI remediation is not required.", scan_url)
elif not ai:
    ai_step = ("waiting", "Waiting for AI remediation workflow to start from the canonical scan.", None)

validation_status = {
    "running": ("running", "AI remediation is still running; validation has not completed."),
    "pass": ("pass", "Sandbox validation and post-fix verification are executed inside the remediation engine."),
    "fail": ("waiting", "Validation was not reached because AI remediation failed."),
    "error": ("waiting", "Validation was not reached because AI remediation ended with an error."),
    "waiting": ("waiting", "Waiting for AI remediation before validation can run."),
}[ai_step[0]]

# A remediation PR is keyed to the source commit, not to the later scan-data publishing commit.
pr = next((
    p for p in prs
    if p.get("head", {}).get("ref", "").startswith(("security/ai-remediation/", "security-remediation/"))
    and (
        p.get("head", {}).get("ref", "").startswith(f"security/ai-remediation/{sha[:12]}")
        or p.get("head", {}).get("ref", "").startswith(f"security-remediation/{sha[:12]}")
        or p.get("head", {}).get("sha") == sha
    )
), None)

if pr:
    pr_state = "pass"
    pr_detail = f"Remediation PR #{pr['number']} is open." if pr.get("state") == "open" else (
        f"Remediation PR #{pr['number']} was merged." if pr.get("merged_at") else
        f"Remediation PR #{pr['number']} is closed without merge."
    )
    pr_url = pr.get("html_url")
else:
    if ai_step[0] == "running":
        pr_state, pr_detail = "waiting", "Waiting for remediation to validate and create the PR."
    elif ai_step[0] == "pass" and not findings:
        pr_state, pr_detail = "pass", "No remediation PR required."
    elif ai_step[0] == "pass":
        pr_state, pr_detail = "waiting", "Remediation completed; waiting for the PR creation step."
    else:
        pr_state, pr_detail = "waiting" if ai_step[0] != "fail" else "fail", "No remediation PR has been created for this commit."
    pr_url = None

# PR security review follows the remediation branch SHA, not the original main SHA.
review = None
if pr:
    review = find_run(runs, {"Security Review"}, pr.get("head", {}).get("sha", ""))
review_jobs = jobs_for(review)
review_step = step_status(review_jobs, "Enforce security gate for review")

if pr:
    review_state, review_detail = review_step[0], review_step[1]
    review_url = review_step[2] or (review or {}).get("html_url")
else:
    review_state, review_detail, review_url = "waiting", "Waiting for a remediation PR.", None

if pr and pr.get("merged_at"):
    human_state, human_detail = "pass", "PR was merged after the automated checks."
elif pr and pr.get("state") == "open":
    human_state, human_detail = "waiting", "Automated checks are represented above; human review is required before merge."
elif not findings:
    human_state, human_detail = "pass", "No human review is required because there was no blocking finding."
else:
    human_state, human_detail = "waiting", "Waiting for a remediation PR requiring human review."

merge_state = (
    "pass" if pr and pr.get("merged_at")
    else "fail" if pr and pr.get("state") == "closed"
    else "waiting"
)
merge_detail = (
    "Merged."
    if merge_state == "pass"
    else "PR closed without merge."
    if merge_state == "fail"
    else "Waiting for merge."
)

stages = [
    ("1. Commit received", "pass", f"Commit {sha[:12]} received.", commit.get("html_url")),
    ("2. Capture exact diff", capture_diff[0], capture_diff[1], capture_diff[2]),
    ("3. Security scan", security[0], security[1], security[2]),
    ("4. AI remediation", ai_step[0], ai_step[1], ai_step[2] or (ai or {}).get("html_url")),
    ("5. Sandbox validation", validation_status[0], validation_status[1], ai_step[2] or (ai or {}).get("html_url")),
    ("6. Post-fix verification", validation_status[0], validation_status[1], ai_step[2] or (ai or {}).get("html_url")),
    ("7. Remediation PR", pr_state, pr_detail, pr_url or (ai or {}).get("html_url")),
    ("8. Full PR security re-scan", review_state, review_detail, review_url),
    ("9. Human review", human_state, human_detail, pr_url),
    ("10. Merge / completed", merge_state, merge_detail, pr_url),
]

current = next(
    (label for label, status, _, _ in stages if status in {"running", "fail", "error", "waiting"}),
    "10. Merge / completed",
)

flow = {
    "schema_version": "2.0",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "current_stage_label": current,
    "source_of_truth": {
        "capture": "data/latest.json or data/scans/<commit>.json",
        "security": "security_engine embedded in canonical scan data",
        "remediation": "GitHub Actions workflow status",
        "review": "GitHub PR Security Review workflow status",
        "merge": "GitHub PR state",
    },
    "scan": {
        "id": (scan or {}).get("scan", {}).get("id"),
        "captured_at": (scan or {}).get("scan", {}).get("captured_at"),
        "files_changed": (scan or {}).get("change_summary", {}).get("files_changed"),
        "additions": (scan or {}).get("change_summary", {}).get("additions"),
        "deletions": (scan or {}).get("change_summary", {}).get("deletions"),
        "findings": len(findings),
        "critical": crit,
        "high": high,
    },
    "commit": {
        "sha": sha,
        "author": commit.get("author", {}).get("login")
        or commit.get("commit", {}).get("author", {}).get("name", "unknown"),
        "branch": "main",
        "message": commit.get("commit", {}).get("message", "").splitlines()[0],
        "url": commit.get("html_url", ""),
    },
    "pull_request": None if not pr else {
        "number": pr["number"],
        "url": pr["html_url"],
        "state": pr["state"],
        "head": pr["head"]["ref"],
        "head_sha": pr["head"]["sha"],
        "base": pr["base"]["ref"],
        "merged": bool(pr.get("merged_at")),
    },
    "stages": [
        {"label": label, "status": status, "detail": detail, "run_url": run_url, "pr_url": pr_url}
        for label, status, detail, run_url in stages
    ],
}

Path(".runtime-flow.json").write_text(json.dumps(flow, indent=2) + "\n", encoding="utf-8")
Path(".runtime-prs.json").write_text(json.dumps(prs, indent=2) + "\n", encoding="utf-8")
print(json.dumps(flow, indent=2))
