# 2026-05-05: Review Fix — Processed Lookup Uses Indexes

## Target

Reduce repeated full-library manifest scans when `creator fetch` or
`creator enqueue` marks discovered entries as `new` or `processed`.

## Changes

- Added creator-index lookup before manifest fallback.
- Reads `library/<platform>/<creator>/_index.json` files for processed video
  ids and source URLs.
- Falls back to manifest scanning only when no creator indexes are available.
- Logs which lookup path was used.
- Added a test proving creator indexes can mark entries as processed without
  completed manifest directories.

## Program Logs

New logs:

```text
[creator] processed lookup: indexes
[creator] processed lookup: manifests
[creator] index lookup skipped (...): ...
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_creators.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
git diff --check
```

Result:

```text
15 passed
191 passed
No broken requirements found.
compileall clean
git diff --check clean
```
