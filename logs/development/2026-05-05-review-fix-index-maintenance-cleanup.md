# 2026-05-05: Review Fix — Index Maintenance Cleanup

## Target

Clean up maintainability issues found in `rebuild_library_indexes()`.

## Changes

- Replaced `_manifest_video_entry()` with `_manifest_video_entries()`.
- Removed the unused `index_root` return value and variable.
- Made the helper return exactly the creator index entry and optional series
  index entry that callers need.
- Simplified `_dedupe_video_entries()` so it only deduplicates entries with a
  real `video_id`.
- Added a rebuild test for manifests missing `video_id`.

## Program Logs

No new program log categories were added. Invalid manifests continue to be
reported through:

```text
[index] skipped manifest (...): ...
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_library.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
git diff --check
```

Result:

```text
73 passed
190 passed
No broken requirements found.
compileall clean
git diff --check clean
```
