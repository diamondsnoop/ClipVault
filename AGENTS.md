# ClipVault Agent Guide

## Project Goal

ClipVault is a local-first video transcript vault. The current priority is reliable acquisition and maintenance of original video transcripts, not AI note generation.

Core workflow:

1. Accept a video URL.
2. Prefer platform-provided subtitles or automatic captions.
3. If no subtitles are available, download audio and run local ASR.
4. Export `srt`, `txt`, and `md`.
5. Store outputs under a stable local library path.

## Current Scope

Implemented:

- Bilibili URL processing through `yt-dlp`.
- YouTube subtitle pipeline validation through `yt-dlp`.
- Platform subtitle extraction when available.
- Audio download fallback.
- Local ASR through `faster-whisper`.
- CUDA auto-selection with CPU fallback.
- Local file outputs:
  - `manifest.json`
  - `transcript.srt`
  - `transcript.txt`
  - `transcript.md`
- Platform-aware creator/video folder layout:
  - `library/<platform>/<creator>/<video title - id>/`
- Legacy cache compatibility for complete old folders:
  - `library/<creator>/<video title - id>/`

Manual series grouping:

- `--series "Series Name"` assigns a video to a series folder.
- Path: `library/<platform>/<creator>/<series>/<video title - id>/`.
- Manifest includes `"series": "Series Name"`.
- This is manual assignment only; no auto-detection, no creator subscriptions.

Auto series rules (Phase 4 Step 3):

- Without `--series`, ClipVault reads `library/<platform>/<creator>/_series_rules.json`.
- Title-based matching via `title_contains` (keyword list) or `title_regex`.
- First matching rule wins; rules evaluated in file order.
- Explicit `--series` always takes priority over auto-rules.
- Rule file must be created manually; no CLI management commands yet.
- This is local title matching, not AI recognition or creator subscription.

Library indexes (auto-maintained):

- `library/<platform>/<creator>/_index.json` — creator index with all videos and series aggregation.
- `library/<platform>/<creator>/<series>/_index.json` — series index (created only when `--series` is used).
- Indexes are updated on both new processing and cache hits.
- Indexes can be rebuilt from completed manifests with `clipvault library rebuild-index`.
- Indexes are plain JSON, no database required.

Creator source registry (Phase 5 Step 1):

- `library/_creators.json` stores creator/channel source URLs for later batch ingestion.
- `clipvault creator add <url> --name "Display Name"` records or updates a source.
- `clipvault creator list` prints recorded sources.
- `clipvault creator fetch <selector>` previews recent entries from a recorded source.
- Fetch entries include `library_status` as `new` or `processed`.
- Fetch preview does not process transcripts or queue ASR jobs yet.

Not yet implemented:

- GUI.
- YouTube/Douyin-specific polish beyond the generic `yt-dlp` path.
- Rule management CLI commands.
- Creator subscriptions.
- Database/indexing.
- AI summary or note generation.

## Repository Layout

- `clipvault/cli.py`: CLI entrypoint and high-level pipeline orchestration.
- `clipvault/platforms.py`: URL metadata extraction and audio download via `yt-dlp`.
- `clipvault/subtitles.py`: Subtitle track selection, download, and parsing.
- `clipvault/asr.py`: `faster-whisper`, CUDA/CPU selection, local model resolution.
- `clipvault/library.py`: File naming, manifest creation, library path helpers.
- `clipvault/series_rules.py`: Title-based auto series rule matching.
- `clipvault/exporters.py`: `srt`, `txt`, and `md` output generation.
- `clipvault/models.py`: Shared dataclasses.
- `clipvault/text.py`: Text cleanup helpers.
- `clipvault.ps1`: Windows convenience launcher.
- `requirements.lock`: Base pinned runtime dependencies.
- `requirements-gpu-win.lock`: Optional Windows NVIDIA GPU runtime dependencies.
- `uv.lock`: uv-generated lock data.

## Local Runtime

This project uses a local `.venv`, but `.venv/` is ignored and must not be committed.

Install base dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

Install optional Windows NVIDIA GPU runtime:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu-win.lock
```

`ffmpeg` must be available on `PATH`.

## Common Commands

Run help:

```powershell
.\clipvault.ps1 --help
```

Process a video:

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..."
```

Force reprocessing:

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --force
```

Group into a series:

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --series "睡前消息"
```

Force CPU:

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device cpu
```

Verify Python dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip check
```

Compile modules:

```powershell
.\.venv\Scripts\python.exe -m compileall clipvault
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Rebuild local indexes without downloading or transcribing:

```powershell
.\clipvault.ps1 library rebuild-index
.\clipvault.ps1 library rebuild-index --dry-run
```

Record and list creator/channel sources:

```powershell
.\clipvault.ps1 creator add "https://www.youtube.com/@Jabzy" --name "Jabzy"
.\clipvault.ps1 creator list
.\clipvault.ps1 creator fetch "Jabzy" --limit 10
```

## Manual Platform Samples

Use these real-world samples when a development task needs manual or integration-style platform validation. Do not make normal unit tests depend on these links or creators; platform pages and subtitles can change.

- Bilibili: 马督公《睡前消息》系列.
- YouTube: Jabzy, `History of the Middle East` series.
- Douyin: 王朝董事会《大明王朝》系列.

When testing with these samples, record the exact URL, date, whether subtitles were platform-provided or ASR-generated, output path, and any platform-specific failure in `logs/development/`.

## Development Rules

- Keep the project focused on transcript acquisition and transcript library maintenance.
- Do not add AI note generation until transcript acquisition and library management are stable.
- Do not commit generated transcripts, audio files, model caches, `.venv/`, or package caches.
- Keep GPU runtime optional; do not force all users to install large NVIDIA packages.
- Preserve existing CLI behavior unless explicitly changing it.
- Prefer small, testable modules over adding more logic to `cli.py`.
- Use UTF-8 for documentation and generated text.
- Every development task must be planned around a clear target and executed step by step. After completing each meaningful step, write a corresponding development log entry under `logs/development/`.
- Code changes must include user-visible program logging where appropriate. Features should report what they are doing, what succeeded, what failed, and enough diagnostic context to make bug reports actionable. Program log conventions and examples belong under `logs/program/`.
- Cache reuse must be based on completed manifest state and actual transcript files, not only on a single marker field or `transcript.md`.
- ASR currently runs with local model files only. Do not write user-facing messages that imply ClipVault will automatically download models unless that behavior is implemented and tested.

## Logs

ClipVault treats logs as part of long-term project maintenance, not disposable notes.

### Development Logs

Development logs live in:

```text
logs/development/
```

Use development logs to record how the project changes over time. Each development task should create or update a dated Markdown file. Recommended naming:

```text
logs/development/YYYY-MM-DD-short-topic.md
```

Each entry should include:

- Target: the concrete goal of the task.
- Steps: the planned steps and what was completed.
- Changes: important modules/files changed.
- Verification: commands, scenarios, and results.
- Follow-ups: unresolved issues or recommended next tasks.

### Program Logs

Program logging guidance lives in:

```text
logs/program/
```

Program logs are about runtime observability. When adding or changing code, make sure the user can understand:

- Which stage is running, such as metadata extraction, subtitle lookup, audio download, ASR, export, or cache reuse.
- What succeeded, including subtitle source, ASR device/model, output paths, and elapsed time when useful.
- What failed, including the operation, error reason, and practical next checks.
- Whether the tool is falling back, such as CUDA to CPU or platform subtitles to ASR.

The current CLI may use simple stderr/stdout messages. As ClipVault grows, prefer a structured logging layer that can later support GUI progress display, log files, and bug reports.

## Open Source Maintenance Standard

Develop ClipVault as a long-lived, professional, friendly open source project:

- Avoid one-off local hacks that only work on a single machine.
- Keep configuration, dependency assumptions, and platform-specific behavior documented.
- Prefer maintainable interfaces over quick coupling.
- Make failures understandable to non-author users.
- Keep public behavior stable unless a change is intentional and documented.
- Leave enough tests, logs, and documentation for future contributors to continue the work safely.

## Git Hygiene

Ignored local/runtime directories include:

- `.venv/`
- `.pip-cache/`
- `.uv-cache/`
- `.tmp/`
- `library/`
- `vendor/wheels/`

Before committing:

```powershell
Remove-Item -LiteralPath clipvault\__pycache__ -Recurse -Force -ErrorAction SilentlyContinue
.\clipvault.ps1 --help
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
git status --short --ignored
```

## Near-Term Roadmap

Recommended next steps:

1. Harden Bilibili behavior with focused real-link regression cases.
2. Add explicit platform abstraction boundaries before adding more platforms.
3. ~~Add series assignment, starting with manual `--series`.~~ (done)
4. ~~Add creator-level indexes after the manifest shape is stable.~~ (done)
5. ~~Add title-based auto series rules.~~ (done)
6. Keep GUI and AI features out of scope until transcript acquisition and library maintenance are dependable.
