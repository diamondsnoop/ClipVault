# 2026-05-05: Review Fix — Flat Entry URL Completion

## Target

Harden `yt-dlp` flat playlist/channel entry URL handling for non-YouTube
platforms.

## Changes

- `_flat_entry_url()` now receives the source creator URL as context.
- Absolute entry URLs are still preferred.
- YouTube ids are converted to `https://www.youtube.com/watch?v=...`.
- Bilibili `BV...` / `av...` ids are converted to
  `https://www.bilibili.com/video/...`.
- Douyin ids are converted to `https://www.douyin.com/video/...`.
- Relative paths are resolved with `urllib.parse.urljoin()`.
- Added tests for YouTube, Bilibili, Douyin, and relative-path behavior.

## Program Logs

No new program log category was added. This fix improves candidate URL quality
inside existing creator fetch logs.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_platforms.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
git diff --check
```

Result:

```text
18 passed
194 passed
No broken requirements found.
compileall clean
git diff --check clean
```
