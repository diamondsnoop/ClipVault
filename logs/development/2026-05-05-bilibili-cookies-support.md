# 2026-05-05: Bilibili Cookies Support

## Target

Add authenticated platform access so Bilibili links that require a logged-in
session can be processed with a local exported cookies file.

## Steps

1. Add a reusable auth boundary.
   - Added `clipvault/auth.py`.
   - Validates the cookies path before use.
   - Passes cookies to `yt-dlp` through `cookiefile`.
   - Loads Netscape cookies for direct subtitle HTTP downloads.

2. Thread cookies through the existing pipelines.
   - `extract_info()` accepts `cookies`.
   - `extract_creator_entries()` accepts `cookies`.
   - `download_audio()` accepts `cookies`.
   - `get_platform_subtitles()` and `fetch_text()` accept `cookies`.
   - `process_video()`, `creator fetch`, `creator enqueue`, and `queue run`
     pass the configured cookies path downstream.

3. Add CLI and documentation.
   - Added `--cookies <path>` as a global option and as a command-local option
     for video, creator fetch/enqueue, and queue run.
   - Updated `.gitignore`, README, AGENTS.md.
   - Added `logs/program/auth-cookies.md`.

4. Add tests.
   - Auth helper validation and cookie loading.
   - yt-dlp option propagation.
   - Subtitle cookie propagation.
   - CLI propagation for video, creator fetch, and queue run.

## Program Logs

New log messages:

- `[auth] cookies file: <path>`
- `[auth] cookies loaded for HTTP requests: <path>`
- `[error] cookies file not found: <path>`
- `[error] failed to load cookies file <path>: <reason>`

Cookie contents are never printed.

## Verification

Relevant test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_auth.py tests\test_subtitles.py tests\test_platforms.py tests\test_cli.py tests\test_creators.py -q
```

Result:

```text
94 passed
```

Note: running pytest inside the filesystem sandbox failed before test assertions
because Python/pytest created temporary directories with Windows ACLs that the
sandboxed process could not reopen. The same command passed in the normal local
environment.

## Follow-ups

- Real Bilibili validation should use a user-provided cookies file stored under
  `.secrets/`.
- If users frequently need browser-cookie import, consider a future explicit
  `--cookies-from-browser` design instead of adding it ad hoc.
