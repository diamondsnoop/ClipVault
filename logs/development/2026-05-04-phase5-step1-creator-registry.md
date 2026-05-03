# 2026-05-04: Phase 5 Step 1 — Creator Source Registry

## Target

Add the first creator tracking foundation: a local registry of creator/channel
source URLs that later batch ingestion can use.

This step intentionally does not fetch recent videos. It only records durable
source metadata.

## Steps

1. Added `clipvault/creators.py` for registry load, add, and list behavior.
2. Added CLI commands:
   - `clipvault creator add <url> --name "Display Name"`
   - `clipvault creator list`
3. Added tests for registry creation, idempotent updates, sorting, invalid
   registry recovery, unknown-platform rejection, and CLI command wrappers.
4. Updated README, roadmap, and agent guidance.

## Changes

- `library/_creators.json` stores:
  - schema version
  - registry type
  - updated time
  - creator records
- Creator records include:
  - stable id
  - platform
  - display name
  - source URL
  - added time
  - last checked time

## Program Logs

Runtime logs added for registry maintenance:

- `[creator] added: ...`
- `[creator] updated: ...`
- `[creator] listed: ...`
- `[creator] registry: ...`
- `[creator] registry load failed (...): ...`
- `[creator] invalid registry shape (...), starting empty`

## Verification

```powershell
.\clipvault.ps1 creator add --help
.\clipvault.ps1 creator list --help
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
git diff --check
```

Result:

```text
172 passed
No broken requirements found.
compileall clean
git diff --check clean
```

## Follow-ups

Next Phase 5 step should add a read-only creator fetch preview that asks
`yt-dlp` for recent entries without processing them. Actual batch ingestion
should remain a separate later step.
