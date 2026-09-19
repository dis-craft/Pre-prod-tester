# Pre-prod Tester

Phase 1 is a CI/CD change-capture pipeline.

## Current architecture

```
git push
   ↓
GitHub Actions
   ↓
git diff (before → after)
   ↓
structured JSON
   ↓
data/scans/<commit>.json
   ↓
GitHub Pages
   ├── /data/latest.json
   ├── /data/index.json
   └── /data/scans/<commit>.json
```

This phase deliberately does **not** perform vulnerability detection yet. It captures the exact code changes and exposes them as machine-readable JSON. Detection engines can be added later without changing the capture contract.

## API-style endpoints

Once GitHub Pages is enabled for this repository:

- `/data/latest.json` — latest captured push
- `/data/index.json` — scan history/index
- `/data/scans/<commit-sha>.json` — immutable scan payload for a commit
- `/` — human-readable viewer

Expected project-site URL:

`https://dis-craft.github.io/Pre-prod-tester/`

## Important

GitHub Pages is a static host, not a server-side API. The JSON endpoints above are static HTTP resources. This is intentional for Phase 1 because it removes database/deployment complexity while giving the CI pipeline a stable URL contract.

For Phase 2, the same JSON contract can be POSTed to a real API (FastAPI/Vercel/other host) and persisted in a database.

## Security

The workflow treats repository changes as data. It does not execute the changed application code, install project dependencies, or run untrusted scripts.

Do not put secrets, credentials, or sensitive source material into the Pages-published scan data. GitHub notes that Pages sites can be publicly accessible even when the source repository is private, depending on the account/plan configuration.
