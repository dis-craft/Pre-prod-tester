# Pre-prod Tester integration

Pre-prod Tester is integrated as a GitHub Actions reusable workflow. It is not an npm dependency because the first-stage operation is Git-aware: it needs the caller repository's commit history and the exact before -> after push range.

## Add it to another repository

Create .github/workflows/preprod.yml:

    name: Pre-prod Tester

    on:
      push:
        branches: [main]

    permissions:
      contents: read

    jobs:
      preprod:
        uses: dis-craft/Pre-prod-tester/.github/workflows/preprod-scan.yml@main
        permissions:
          contents: read

The reusable workflow checks out the calling repository, captures the exact Git diff, and uploads a machine-readable artifact.

## Output

The action writes .preprod/scan.json and the workflow uploads it as preprod-scan-<commit-sha>.

The JSON contains repository and commit metadata, before/after SHAs, changed-file summary, exact additions/deletions, GitHub-style hunks, line-by-line records, raw unified diff, and security-engine placeholders.

## Why GitHub Actions instead of npm?

npm is useful for a local CLI, but GitHub Actions is the native integration point for a push-triggered CI/CD scanner. The target repository only needs a small workflow file while the scanner implementation stays centralized.

Later this same workflow can POST the generated JSON to the detection API:

    target repo push
        |
        v
    Pre-prod Tester reusable workflow
        |
        v
    structured scan JSON
        |
        v
    POST /v1/scans
        |
        v
    vulnerability detection

Because Pre-prod Tester is currently private, its repository Actions settings must allow other repositories to access its reusable workflow/action.
