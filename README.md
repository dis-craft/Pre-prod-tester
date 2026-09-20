# Pre-Prod Tester

> **Pre-Prod Tester** is the change-capture, security-scan, remediation-trigger, and live-flow data layer for the Pre-Prod security system.
>
> This repository is the **caller/integration repository**. The reusable security/remediation engine lives in **[Pre-Prod-Orchestrator](https://github.com/dis-craft/Pre-Prod-Orchestrator)**.

---

## 1. What this repository does

The production path watches changes pushed to `main`, captures the **exact Git diff**, runs canonical security detection, stores the result as machine-readable JSON, triggers AI remediation when blocking findings exist, and publishes live pipeline state for the website.

```
Developer change
      |
      v
GitHub push to main
      |
      v
Pre-Prod Tester
  ├─ Capture exact before → after diff
  ├─ Run security detection
  ├─ Persist canonical scan JSON
  ├─ Publish static scan data
  └─ Call Pre-Prod-Orchestrator
          |
          ├─ Gemini remediation
          ├─ Sandbox validation
          ├─ Post-fix verification
          ├─ Repository tests
          └─ Remediation PR
                    |
                    v
             Security Review
                    |
                    v
              Human review
                    |
                    v
                  Merge
```

The **website does not perform the scan again**. It consumes canonical scan data plus GitHub workflow/PR state.

---

## 2. The two repositories

### Repository A — Pre-Prod Tester

https://github.com/dis-craft/Pre-prod-tester

Owns:

- Git change capture
- canonical scan JSON
- GitHub Pages website
- live flow JSON
- integration workflows
- connection into the orchestrator

Mental model:

> **What changed, what was detected, what is happening, and what should the website display?**

### Repository B — Pre-Prod Orchestrator

https://github.com/dis-craft/Pre-Prod-Orchestrator

Owns:

- security scanning/normalization
- AI remediation
- Gemini integration
- remediation retry/fallback
- sandbox validation
- post-remediation verification
- reusable security workflow

Mental model:

> **How do we detect, fix, validate, and verify the security issue?**

The tester repository invokes the orchestrator through reusable GitHub Actions workflows/actions.

---

## 3. Public websites

Main website:

https://dis-craft.github.io/Pre-prod-tester/

Live flow:

https://dis-craft.github.io/Pre-prod-tester/flow.html

GitHub Pages is a **static host**. There is no server-side application behind the Pages site.

GitHub Actions generates JSON files into `data/`, and the HTML/JavaScript reads those JSON files with `fetch()`.

---

## 4. Website → source-code map

| URL | Source | Purpose |
|---|---|---|
| `/` | `index.html` | Main diff/history viewer |
| `/flow.html` | `flow.html` | Live pipeline flow |
| `/data/latest.json` | Generated | Latest canonical scan |
| `/data/index.json` | Generated | Scan history/index |
| `/data/scans/<SHA>.json` | Generated | Immutable per-commit scan |
| `/data/flow.json` | Generated | Current live flow state |
| `/data/pull-requests.json` | Generated | PR snapshot used by flow state |

Do **not** hand-edit generated files under `data/`. Workflows regenerate them.

---

## 5. Main website: index.html

File:

```
index.html
```

URL:

https://dis-craft.github.io/Pre-prod-tester/

It:

1. Fetches `data/latest.json`
2. Shows repository/branch/commit information
3. Shows changed-file counts
4. Renders additions/deletions and diff hunks
5. Fetches `data/index.json`
6. Loads historical scan records
7. Shows commit/security history
8. Links back to GitHub commits/comparisons

The browser **renders** the diff; it does not calculate the underlying Git diff.

The diff is created by `scripts/capture-diff.py`.

---

## 6. Live flow website: flow.html

File:

```
flow.html
```

URL:

https://dis-craft.github.io/Pre-prod-tester/flow.html

It displays:

```
1. Commit received
2. Capture exact diff
3. Security scan
4. AI remediation
5. Sandbox validation
6. Post-fix verification
7. Remediation PR
8. Full PR security re-scan
9. Human review
10. Merge / completed
```

It fetches:

```
data/flow.json
```

and auto-refreshes every 8 seconds.

It does **not** run security logic, Gemini, Git commands, or source analysis.

---

## 7. Canonical scan data

The source-of-truth files are:

```
data/scans/<commit-sha>.json
data/latest.json
```

The immutable per-commit scan is the important historical record.

It contains:

- commit metadata
- before/after SHAs
- changed files
- additions/deletions
- diff hunks
- added/removed line records
- security results
- scanner metadata

Security results are stored under:

```
security_engine
```

The latest scan is exposed through:

```
data/latest.json
```

while historical scans are kept at:

```
data/scans/<SHA>.json
```

---

## 8. Exact diff capture

File:

```
scripts/capture-diff.py
```

This is the source of truth for **what changed**.

It receives the GitHub push range:

```
before SHA → after SHA
```

and uses Git to capture the exact change.

It records:

- file status
- additions
- deletions
- language
- unified diff
- hunks
- added lines
- removed lines
- context lines

It excludes generated data:

```
data/**
.git/**
```

and does not execute changed application code.

It creates:

```
data/latest.json
data/index.json
data/scans/<SHA>.json
```

---

## 9. Main production workflow

File:

```
.github/workflows/capture-and-publish.yml
```

Workflow name:

```
Capture Changes and Publish
```

Trigger:

```
push → main
```

with `data/**` ignored so generated publication commits do not recursively trigger normal scanning.

This workflow contains two jobs:

### Job 1: capture-and-publish

```
checkout
  ↓
capture exact diff
  ↓
security detection
  ↓
attach findings
  ↓
build live flow state
  ↓
snapshot data
  ↓
publish data/
```

### Job 2: remediation

Calls:

```
dis-craft/Pre-Prod-Orchestrator/.github/workflows/preprod-security.yml@main
```

---

## 10. Checkout and exact diff

The production workflow checks out full history:

```
fetch-depth: 0
```

because it needs the real before/after commit range.

Then it runs:

```
python3 scripts/capture-diff.py
```

At this point the canonical scan exists before downstream remediation starts.

---

## 11. Security detection

The production workflow calls the security engine from:

```
Pre-Prod-Orchestrator/.github/actions/security-engine/action.yml
```

with the canonical scan as input.

The design is:

```
Git change
   ↓
canonical scan
   ↓
security detection
   ↓
security findings
```

rather than having each downstream stage independently reconstructing the change.

---

## 12. Attaching findings

File:

```
scripts/attach-security-findings.py
```

The scanner returns normalized findings and metadata.

This script inserts them into the canonical scan under:

```
security_engine
```

and also updates:

```
data/scans/<SHA>.json
```

so the immutable per-commit artifact contains the security results.

Therefore:

```
latest.json
```

and the corresponding:

```
scans/<SHA>.json
```

agree about that scan's findings.

---

## 13. Why per-commit scans exist

If commit `ABC123` is scanned and a later commit `DEF456` is pushed:

```
data/latest.json
```

moves to `DEF456`.

But:

```
data/scans/ABC123....json
```

still describes `ABC123`.

This gives the system an immutable historical record.

---

## 14. Live flow state generation

File:

```
scripts/build-dashboard-flow.py
```

This is the bridge between GitHub's real state and the static dashboard.

It reads:

- canonical scan JSON
- GitHub Actions workflow runs
- workflow jobs/steps
- remediation PRs
- PR security review state
- PR merge state

It produces:

```
.runtime-flow.json
.runtime-prs.json
```

which are then published as:

```
data/flow.json
data/pull-requests.json
```

### Important design rule

The dashboard flow **does not recapture the diff or rerun the scanner**.

It uses:

```
canonical scan data
+
GitHub workflow state
+
GitHub PR state
```

as its sources of truth.

---

## 15. Live flow publisher

File:

```
.github/workflows/publish-flow-state.yml
```

It listens for completed runs of:

- `Capture Changes and Publish`
- `AI Security Remediation`
- `Security Review`

and then rebuilds the live flow state.

It intentionally uses:

```
workflow_run:
  types: [completed]
```

so the website is updated from completed GitHub state rather than publishing premature intermediate workflow events.

It writes:

```
data/flow.json
data/pull-requests.json
```

back to `main`.

---

## 16. The actual orchestrator workflow

Repository:

https://github.com/dis-craft/Pre-Prod-Orchestrator

Primary reusable workflow:

```
.github/workflows/preprod-security.yml
```

Primary security action:

```
.github/actions/security-engine/action.yml
```

The tester calls the reusable workflow with inputs such as:

- `generate-remediation`
- `test-command`
- `fallback-model`
- `primary-attempts`
- `fallback-attempts`
- `full-repo-rescan`
- `scan-input`
- `source-sha`
- `reuse-findings`

---

## 17. Reusing canonical findings

The production tester passes:

```
reuse-findings: true
```

and points the orchestrator at:

```
data/scans/<SHA>.json
```

The orchestrator loads:

```
security_engine.findings
```

instead of performing another baseline scan.

This prevents:

- duplicate scanning
- inconsistent results between stages
- unnecessary runtime
- dashboard/pipeline disagreement

The rule is:

> **Capture and baseline security detection happen once. Downstream remediation consumes the canonical result.**

---

## 18. Security engine action

File:

```
Pre-Prod-Orchestrator/.github/actions/security-engine/action.yml
```

It supports two modes:

### Normal scan

Run the scanner.

### Canonical reuse

Load already-persisted findings from the canonical artifact.

The main production path uses both, at different points:

```
initial canonical detection
        ↓
canonical findings
        ↓
reuse findings during remediation
```

---

## 19. Blocking findings

The pipeline treats:

```
HIGH
CRITICAL
```

as blocking findings.

These are the findings that require remediation/security-gate handling.

---

## 20. AI remediation

Main files in the orchestrator:

```
remediation/remediation_agent.py
remediation/ci_entrypoint.py
remediation/retry_pipeline.py
```

The agent receives:

- finding ID
- rule
- CWE
- severity
- file
- line
- category
- message
- fix guidance
- repository context
- relevant source context

Gemini returns a structured edit proposal.

Conceptually:

```json
{
  "edits": [
    {
      "file": "src/example.js",
      "start_line": 10,
      "end_line": 10,
      "original": "...",
      "replacement": "...",
      "explanation": "..."
    }
  ]
}
```

The agent verifies that the returned original text actually matches the file before applying it.

---

## 21. Gemini model and secret

The production remediation action is configured for:

```
gemini-3.5-flash
```

The fallback model is configurable and is currently supplied by the workflow as:

```
gemini-2.5-flash
```

The key is:

```
GEMINI_API_KEY
```

and comes from GitHub Actions secrets.

Never commit the key into source code or publish it into `data/`.

---

## 22. Remediation retries

File:

```
Pre-Prod-Orchestrator/remediation/retry_pipeline.py
```

The retry flow is roughly:

```
canonical finding
      ↓
Gemini attempt
      ↓
apply fix
      ↓
post-fix security verification
      ↓
sandbox validation
      ↓
pass?
  ├─ yes → continue
  └─ no  → reset to original source commit
             ↓
          retry/fallback
```

The repository is reset before another attempt so failed edits do not compound.

---

## 23. Post-fix verification

The system does not trust the AI merely because it produced an edit.

After applying the fix, it calculates the remediation change relative to the original source commit and scans that change.

The goal is to prove:

1. the original blocking finding is gone
2. the fix did not introduce another blocking finding

The post-fix check intentionally focuses on the remediation diff instead of treating unrelated historical repository content as newly introduced vulnerabilities.

---

## 24. Sandbox validation

File:

```
Pre-Prod-Orchestrator/remediation/sandbox_validate.py
```

Changed Python/JavaScript/shell files can be checked in disposable Docker containers.

Examples:

```
python:3.12-slim
node:22-bookworm
bash:5.2
```

The containers use:

```
--network none
```

The goal is lightweight syntax validation in a disposable environment instead of executing untrusted project code on the persistent control plane.

---

## 25. Repository tests

The remediation workflow can run an explicit repository test command.

If none is supplied, it has generic detection for common Node/Python repositories.

There are therefore two distinct verification concepts:

### Security verification

Did the blocking finding disappear?

### Software verification

Do the repository's tests still pass?

Both are part of the remediation pipeline.

---

## 26. Remediation branch and PR

After successful remediation, the orchestrator creates a branch like:

```
security/ai-remediation/<source-sha-prefix>
```

The branch is based on the exact source commit that triggered the remediation.

Then it:

1. commits the fix
2. pushes the branch
3. creates a pull request

The PR is **not automatically merged**.

---

## 27. PR security review

File:

```
.github/workflows/security-review.yml
```

This workflow runs on:

- PR opened
- PR synchronized
- PR reopened

It calls:

```
Pre-Prod-Orchestrator/.github/workflows/preprod-security.yml
```

with:

```
generate-remediation: false
full-repo-rescan: true
```

This asks a different question:

> **Is the proposed remediation PR itself security-clean?**

So there are two security phases:

```
main commit
   ↓
baseline security detection
   ↓
AI remediation
   ↓
remediation PR
   ↓
PR security re-scan
```

---

## 28. Human review is deliberate

Automated stages include:

- change capture
- security detection
- AI remediation
- sandbox validation
- post-fix verification
- repository tests
- remediation PR creation
- PR security scan

The final approval remains human.

The architecture explicitly avoids automatically merging AI-generated security fixes.

---

## 29. No findings path

If the baseline scan has no blocking HIGH/CRITICAL findings:

```
Commit
 ↓
Diff capture
 ↓
Security scan
 ↓
No blocking findings
 ↓
No AI remediation
 ↓
No remediation PR required
 ↓
Flow can complete
```

The system does not create a remediation PR just to force the flow to continue.

---

## 30. Failure/retry path

If remediation fails:

```
source commit
   ↓
AI attempt
   ↓
validation
   ↓
failure
   ↓
reset to source
   ↓
retry / fallback
```

If all attempts fail, the system does not claim success.

The flow remains in a failed/waiting state until another valid action occurs.

---

## 31. Other workflows in Pre-Prod Tester

### `.github/workflows/capture-and-publish.yml`

**Primary production path.**

Normal `main` pushes enter here.

### `.github/workflows/publish-flow-state.yml`

**Live state publisher.**

Updates:

```
data/flow.json
data/pull-requests.json
```

### `.github/workflows/security-review.yml`

**PR security gate.**

Runs against remediation pull requests.

### `.github/workflows/preprod-scan.yml`

**Reusable diff-capture workflow.**

Another repository can call it to produce a structured `.preprod/scan.json` artifact.

### `.github/workflows/full-security-pipeline.yml`

**Integration/full pipeline test path.**

Used for dedicated full-pipeline testing.

### `.github/workflows/live-remediation-test.yml`

**Remediation smoke-test path.**

Used for dedicated security/remediation test branches.

### `.github/workflows/remediation.yml`

**Older/manual remediation integration.**

It builds a remediation request, calls an external orchestrator endpoint, applies the returned patch, runs tests, and creates a remediation PR.

The current main production path does **not** depend on this older workflow; the production path uses the reusable workflow in Pre-Prod-Orchestrator directly.

---

## 32. Scripts directory

```
scripts/
├── capture-diff.py
├── attach-security-findings.py
├── build-dashboard-flow.py
└── remediation-payload.py
```

### `capture-diff.py`

Exact Git before→after diff → canonical JSON.

### `attach-security-findings.py`

Adds normalized scanner findings to canonical scan data.

### `build-dashboard-flow.py`

GitHub workflow/PR state + canonical scan → dashboard state.

### `remediation-payload.py`

Builds the payload used by the older/manual remediation workflow.

---

## 33. Data directory

```
data/
├── latest.json
├── index.json
├── flow.json
├── pull-requests.json
└── scans/
    └── <commit>.json
```

### `latest.json`

Convenience pointer to the newest canonical scan.

### `index.json`

Historical index of captured commits/scans.

### `scans/<SHA>.json`

Immutable per-commit scan record.

### `flow.json`

Current live pipeline state.

### `pull-requests.json`

GitHub PR snapshot used by the flow state.

---

## 34. Current source tree

```
Pre-prod-tester/
│
├── .github/
│   └── workflows/
│       ├── capture-and-publish.yml       # Main production pipeline
│       ├── publish-flow-state.yml       # Publishes live flow JSON
│       ├── security-review.yml          # PR security gate
│       ├── preprod-scan.yml             # Reusable diff capture
│       ├── full-security-pipeline.yml   # Full/integration test path
│       ├── live-remediation-test.yml    # Remediation smoke test
│       └── remediation.yml              # Older/manual remediation path
│
├── scripts/
│   ├── capture-diff.py                   # Exact Git diff → canonical JSON
│   ├── attach-security-findings.py       # Attach scanner findings
│   ├── build-dashboard-flow.py           # GitHub state → flow state
│   └── remediation-payload.py            # Legacy remediation payload
│
├── data/
│   ├── latest.json                       # Latest canonical scan
│   ├── index.json                        # Scan history
│   ├── flow.json                         # Live flow state
│   ├── pull-requests.json                # PR state snapshot
│   └── scans/
│       └── <commit>.json                 # Immutable per-commit scans
│
├── index.html                            # Main GitHub Pages UI
├── flow.html                             # Live flow UI
├── PREPROD-INTEGRATION.md                # Reusable-workflow integration guide
├── Jenkinsfile                           # Additional/legacy Jenkins path
└── README.md                             # This document
```

---

## 35. Where to edit what

| Goal | Edit |
|---|---|
| Change main diff viewer UI | `index.html` |
| Change live pipeline UI | `flow.html` |
| Change data presented to flow UI | `scripts/build-dashboard-flow.py` |
| Change exact Git diff capture | `scripts/capture-diff.py` |
| Change how findings are attached | `scripts/attach-security-findings.py` |
| Change main production trigger/orchestration | `.github/workflows/capture-and-publish.yml` |
| Change when flow JSON gets published | `.github/workflows/publish-flow-state.yml` |
| Change PR security review behavior | `.github/workflows/security-review.yml` |
| Change actual scanner/security engine | **Pre-Prod-Orchestrator** |
| Change Gemini remediation behavior | `Pre-Prod-Orchestrator/remediation/remediation_agent.py` |
| Change remediation retries/verification | `Pre-Prod-Orchestrator/remediation/retry_pipeline.py` |
| Change sandbox validation | `Pre-Prod-Orchestrator/remediation/sandbox_validate.py` |

---

## 36. Source-of-truth rules

| Information | Source of truth |
|---|---|
| What changed | `data/scans/<SHA>.json` |
| Latest scan | `data/latest.json` |
| Scan history | `data/index.json` |
| Security findings | `security_engine` in canonical scan |
| AI remediation state | GitHub Actions |
| Sandbox result | Remediation workflow |
| Post-fix verification | Remediation workflow |
| Remediation PR | GitHub PR |
| PR security review | Security Review workflow |
| Human review | GitHub PR review state |
| Merge state | GitHub PR state |
| What the website displays | Generated JSON consumed by the HTML |

The most important rule:

> **Do not make the frontend a second security engine.**

---

## 37. Why the architecture is split

### Reproducibility

Every source commit gets a persistent scan record.

### Consistency

Remediation can reuse the exact findings generated by the canonical scan.

### Separation of concerns

- HTML = presentation
- GitHub Actions = orchestration
- Orchestrator = security/remediation
- GitHub PR = human approval boundary
- GitHub Pages = static delivery

### Auditability

The system preserves the chain:

```
source commit
→ finding
→ AI fix
→ validation
→ remediation PR
→ PR re-scan
→ review
→ merge
```

---

## 38. Reusable integration from another repository

See:

```
PREPROD-INTEGRATION.md
```

The reusable capture workflow is:

```
dis-craft/Pre-prod-tester/.github/workflows/preprod-scan.yml@main
```

A target repository can call it from its own GitHub Actions workflow.

The target repository does not need to install Pre-Prod Tester as an npm package.

Why?

Because the first stage is inherently Git-aware and needs the caller repository's commit history and before→after range.

The reusable workflow:

1. checks out the caller repository
2. captures the exact change
3. writes `.preprod/scan.json`
4. uploads the result as a workflow artifact

---

## 39. GitHub Pages vs API server

Current design:

```
GitHub Actions
      ↓
generated JSON committed to repo
      ↓
GitHub Pages
      ↓
browser fetch()
```

For example:

```
https://dis-craft.github.io/Pre-prod-tester/data/latest.json
```

is just a static JSON resource.

A future backend could replace the storage layer with:

```
GitHub Actions
      ↓
POST /api/scans
      ↓
database
      ↓
frontend
```

without changing the conceptual scan contract.

---

## 40. Typical developer lifecycle

```
1. Developer changes code
2. Pushes to main
3. Capture workflow starts
4. Exact before→after diff is captured
5. Security detection runs
6. Findings are written into canonical scan JSON
7. If HIGH/CRITICAL findings exist, remediation starts
8. Gemini proposes minimal edits
9. Edits are verified
10. Sandbox validation runs
11. Post-fix security verification runs
12. Repository tests run
13. Remediation branch/PR is created
14. PR security review runs
15. Human reviews
16. Human merges
17. Live website state updates throughout
```

---

## 41. Full architecture diagram

```
                         ┌─────────────────────┐
                         │   Developer change  │
                         └──────────┬──────────┘
                                    │
                                    v
                         ┌─────────────────────┐
                         │   GitHub main push  │
                         └──────────┬──────────┘
                                    │
                                    v
              ┌────────────────────────────────────────┐
              │         Pre-Prod Tester repo           │
              │                                        │
              │ capture-and-publish.yml                │
              │          │                             │
              │          v                             │
              │ scripts/capture-diff.py                │
              │          │                             │
              │          v                             │
              │ canonical scan                         │
              │ data/scans/<SHA>.json                  │
              │          │                             │
              │          v                             │
              │ security detection                     │
              │          │                             │
              │          v                             │
              │ attach-security-findings.py             │
              └──────────┬─────────────────────────────┘
                         │
                         │ reusable workflow
                         v
              ┌────────────────────────────────────────┐
              │      Pre-Prod-Orchestrator repo        │
              │                                        │
              │ preprod-security.yml                   │
              │          │                             │
              │          v                             │
              │ security-engine/action.yml              │
              │          │                             │
              │          v                             │
              │ remediation/retry_pipeline.py           │
              │          │                             │
              │          v                             │
              │ remediation/remediation_agent.py        │
              │          │                             │
              │          v                             │
              │             Gemini                     │
              │          │                             │
              │          v                             │
              │ sandbox_validate.py                    │
              │          │                             │
              │          v                             │
              │ post-fix verification                  │
              └──────────┬─────────────────────────────┘
                         │
                         v
                 remediation branch
                         │
                         v
                    GitHub PR
                         │
                         v
              security-review.yml
                         │
                         v
                 PR security scan
                         │
                         v
                  human review
                         │
                         v
                       merge

Meanwhile:

GitHub workflow state
        +
canonical scan JSON
        +
GitHub PR state
        │
        v
build-dashboard-flow.py
        │
        v
data/flow.json
        │
        v
GitHub Pages
        │
        ├── index.html
        └── flow.html
```

---

## 42. One-line mental model

```
Pre-Prod Tester
= capture + canonical data + GitHub orchestration + website state

Pre-Prod Orchestrator
= scan + AI fix + validation + verification

GitHub Actions
= execution engine

GitHub PR
= human approval boundary

GitHub Pages
= static visualization of generated state
```

---

## 43. Related documentation

- [Pre-Prod Tester](https://github.com/dis-craft/Pre-prod-tester)
- [Pre-Prod Orchestrator](https://github.com/dis-craft/Pre-Prod-Orchestrator)
- [Pre-Prod Integration](./PREPROD-INTEGRATION.md)
- [Live Flow](./flow.html)
- [Main dashboard](./index.html)

---

## 44. Security notes

The workflow treats repository changes as data during the capture stage.

Do not publish:

- secrets
- credentials
- API keys
- sensitive source material

into GitHub Pages data.

GitHub Pages is a static/public HTTP surface depending on repository/account configuration, so everything under the published Pages tree should be treated as potentially public.

---
