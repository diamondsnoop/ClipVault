# 2026-05-05: Platform Adapter Boundary

## Target

Create an explicit platform adapter boundary before adding more platform-specific
behavior.

## Changes

- Added `clipvault/adapters.py`.
- Introduced `PlatformAdapter` for:
  - platform name
  - matching domains
  - preferred subtitle languages
  - flat creator-entry URL completion
- Added specialized adapters for:
  - Bilibili
  - YouTube
  - Douyin
- Kept `clipvault/platforms.py` as the `yt-dlp` integration layer.
- Kept compatibility exports (`PLATFORMS`, `identify_platform`,
  `platform_languages`, `_flat_entry_url`) in `platforms.py`.
- Added adapter tests.

## Program Logs

No runtime log categories changed in this step. This is an internal boundary
refactor.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_adapters.py tests\test_platforms.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
git diff --check
```

Result:

```text
26 passed
202 passed
No broken requirements found.
compileall clean
git diff --check clean
```
