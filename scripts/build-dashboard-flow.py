#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
SERVER = os.environ.get("GITHUB_SERVER_URL", "https://github.com")

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
            if step.get("name") == step_name:
                status = step.get("status")
                conclusion = step.get("conclusion")
                if status in {"queued", "in_progress"}:
                    return "running", f"{step_name} is running.", job.get("html_url")
                if conclusion == "success":
                    return "pass", f"{step_name} completed successfully.", job.get("html_url")
                if conclusion in {"cancelled", "timed_out"}:
                    return "error", f"{step_name} ended as {conclusion}.", job.get("html_url")
                if conclusion:
                    return "fail", f"{step_name} ended as {conclusion}.", job.get("html_url")
    return "waiting", f"Waiting for {step_name}.", None

def event_sha():
    name = os.environ.get("GITHUB_EVENT_NAME", "")
    path = os.environ.get("GITHUB_EVENT_PATH", "")
    payload = {}
    if path and Path(path).exists():
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if name == "workflow_run":
        return payload.get("workflow_run", {}).get("head_sha") or os.environ["GITHUB_SHA"]
    if name == "pull_request":
        return payload.get("pull_request", {}).get("head", {}).get("sha") or os.environ["GITHUB_SHA"]
    return os.environ["GITHUB_SHA"]

sha = event_sha()
commit = api(f"/commits/{sha}")
runs = api("/actions/runs?per_page=100&sort=created&direction=desc")
prs = api("/pulls?state=all&per_page=100&sort=updated&direction=desc")

capture = find_run(runs, {"Capture Changes and Publish"}, sha)
ai = find_run(runs, {"AI Security Remediation"}, sha)
review = find_run(runs, {"Security Review"}, sha)

pr = next((
    p for p in prs
    if p.get("head", {}).get("ref", "").startswith(("security/ai-remediation/", "security-remediation/"))
    and (p.get("head", {}).get("sha") == sha or sha[:12] in p.get("head", {}).get("ref", ""))
), None)

capture_jobs = jobs_for(capture)
ai_jobs = jobs_for(ai)
review_jobs = jobs_for(review)

capture_diff = step_status(capture_jobs, "Capture exact push diff")
security = step_status(capture_jobs, "Run live security detection")
ai_step = step_status(ai_jobs, "Run scanner and AI remediation")
tests = step_status(ai_jobs, "Run repository tests")
pr_step = step_status(ai_jobs, "Create remediation branch and PR")
review_step = step_status(review_jobs, "Enforce security gate for review")

if not ai:
    ai_step = ("waiting", "Waiting for AI remediation workflow to start for this commit.", None)

if pr:
    pr_state = "pass" if pr.get("merged_at") else ("running" if pr.get("state") == "open" else "fail")
    pr_detail = f"PR #{pr['number']} is {pr.get('state')}{' and merged' if pr.get('merged_at') else ''}."
    pr_url = pr.get("html_url")
else:
    pr_state = "waiting" if ai_step[0] != "fail" else "fail"
    pr_detail = "No remediation PR has been created for this commit."
    pr_url = None

review_state = review_step[0] if pr else "waiting"
review_detail = review_step[1] if pr else "Waiting for a remediation PR."
if pr and not review and pr.get("state") == "open":
    review_state = "waiting"
    review_detail = "Waiting for the PR security-review workflow."

human_state = "waiting"
human_detail = "No remediation PR requiring human review."
if pr and pr.get("state") == "open":
    human_state = "waiting"
    human_detail = "Waiting for automated PR review and human approval."
elif pr and pr.get("merged_at"):
    human_state = "pass"
    human_detail = "PR was merged after automated checks."

merge_state = "pass" if pr and pr.get("merged_at") else ("fail" if pr and pr.get("state") == "closed" else "waiting")
merge_detail = "Merged." if merge_state == "pass" else ("PR closed without merge." if merge_state == "fail" else "Waiting for merge.")

stages = [
    ("1. Commit received", "pass", f"Commit {sha[:12]}.", commit.get("html_url")),
    ("2. Capture exact diff", capture_diff[0], capture_diff[1], capture_diff[2] or (capture or {}).get("html_url")),
    ("3. Security scan", security[0], security[1], security[2] or (capture or {}).get("html_url")),
    ("4. AI remediation", ai_step[0], ai_step[1], ai_step[2] or (ai or {}).get("html_url")),
    ("5. Sandbox validation", "pass" if ai_step[0] == "pass" else ai_step[0] if ai_step[0] in {"running","fail","error"} else "waiting", "Validation is performed inside the remediation stage.", ai_step[2] or (ai or {}).get("html_url")),
    ("6. Post-fix scan", "pass" if ai_step[0] == "pass" else ai_step[0] if ai_step[0] in {"running","fail","error"} else "waiting", "The modified repository is rescanned before a PR is created.", ai_step[2] or (ai or {}).get("html_url")),
    ("7. Remediation PR", pr_state, pr_detail, pr_url or (ai or {}).get("html_url")),
    ("8. Full PR security re-scan", review_state, review_detail, review_step[2] or (review or {}).get("html_url")),
    ("9. Human review", human_state, human_detail, pr_url),
    ("10. Merge / completed", merge_state, merge_detail, pr_url),
]

running = next((s for s in stages if s[1] == "running"), None)
failed = next((s for s in stages if s[1] in {"fail", "error"}), None)
current = running[0] if running else (failed[0] if failed else "10. Merge / completed" if merge_state == "pass" else "9. Human review" if pr else "4. AI remediation")

flow = {
    "schema_version": "1.3",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "current_stage_label": current,
    "commit": {
        "sha": sha,
        "author": commit.get("author", {}).get("login") or commit.get("commit", {}).get("author", {}).get("name", "unknown"),
        "branch": "main",
        "message": commit.get("commit", {}).get("message", "").splitlines()[0],
        "url": commit.get("html_url", ""),
    },
    "pull_request": None if not pr else {
        "number": pr["number"],
        "url": pr["html_url"],
        "state": pr["state"],
        "head": pr["head"]["ref"],
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
