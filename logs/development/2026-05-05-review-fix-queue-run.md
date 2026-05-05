# 2026-05-05: Review Fix — Queue Execution Commands

## Target

Fix the review finding that `creator enqueue` created pending jobs without any
user-facing way to inspect or execute them.

## Changes

- Added top-level `clipvault queue` commands:
  - `queue list`
  - `queue status`
  - `queue run`
- `queue run` processes pending jobs through the existing `process_video()`
  pipeline.
- `queue run` defaults to `--limit 1` to avoid accidental bulk downloads or ASR.
- Successful jobs are marked `done`.
- Failed jobs are marked `failed` with `last_error`.
- Added tests for listing, status summaries, successful runs, and failed runs.
- Updated README, roadmap, AGENTS, and program logging guidance.

## Program Logs

New queue runtime logs:

- `[queue] listed: ...`
- `[queue] status: ...`
- `[queue] running: ...`
- `[queue] job start: ...`
- `[queue] job done: ...`
- `[queue] job failed: ...`

## Verification

```powershell
.\clipvault.ps1 --help
.\clipvault.ps1 queue --help
.\.venv\Scripts\python.exe -m pytest tests\test_cli.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
git diff --check
```

Result:

```text
top-level help shows queue
queue help shows list/status/run
21 passed
189 passed
No broken requirements found.
compileall clean
git diff --check clean
```
