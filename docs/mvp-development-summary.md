# ClipVault MVP Development Summary

## Conclusion

ClipVault MVP is functionally complete against the current plan.

The MVP goal was not to build an AI note-taking product yet. The goal was to prove and stabilize a local-first transcript vault:

1. Accept a video URL.
2. Prefer platform subtitles or automatic captions.
3. Fall back to local ASR when subtitles are unavailable.
4. Export `srt`, `txt`, and `md`.
5. Store outputs in a maintainable library structure.
6. Support creator/series organization and basic batch ingestion.
7. Provide a simple desktop UI over the same core pipeline.

This has been implemented and manually validated for:

- YouTube: Jabzy `History of the Middle East`, automatic captions, 983 segments.
- Bilibili: 一条闲木鱼《大明王朝》, no platform subtitle, CUDA ASR fallback, 1290 segments.

Douyin is recognized and routed as a platform, but real-link validation is not yet stable because current `yt-dlp` extraction requires fresh Douyin cookies. Treat Douyin as prototype support, not a stable MVP path.

## What Was Completed

### Phase 1: Transcript Core

Completed.

Implemented a reliable single-video transcript pipeline:

- Metadata extraction through `yt-dlp`.
- Platform subtitle discovery.
- Subtitle parsing for Bilibili JSON, YouTube JSON3, VTT, and SRT.
- Audio download fallback.
- Local ASR through `faster-whisper`.
- CUDA auto-selection with CPU fallback.
- Export to `transcript.srt`, `transcript.txt`, and `transcript.md`.
- User-visible program logs for metadata, subtitles, audio download, ASR, export, cache, and index stages.

### Phase 2: Library and Metadata

Completed.

The output layout was moved to:

```text
library/<platform>/<creator>/<video title - id>/
```

With manual or automatic series assignment:

```text
library/<platform>/<creator>/<series>/<video title - id>/
```

Each video folder contains:

```text
manifest.json
transcript.srt
transcript.txt
transcript.md
source_audio.m4a   # only when --keep-audio is used
```

`manifest.json` is the stable metadata record for cache, indexes, and UI browsing. Cache completion checks both manifest state and actual output files.

### Phase 3: Platform Path

Completed for Bilibili and YouTube. Prototype only for Douyin.

- Bilibili is the primary validated path.
- YouTube subtitles and automatic captions have been validated.
- Douyin URL recognition and adapter helpers exist, but stable transcript extraction still depends on platform access/cookies.

### Phase 4: Series and Indexes

Completed.

Implemented:

- Manual `--series`.
- Creator indexes: `library/<platform>/<creator>/_index.json`.
- Series indexes: `library/<platform>/<creator>/<series>/_index.json`.
- `library rebuild-index`.
- Title-based auto series rules through `_series_rules.json`.

Series rules are local JSON files:

```text
library/<platform>/<creator>/_series_rules.json
```

Example:

```json
{
  "schema_version": 1,
  "rules": [
    {
      "series": "History of the Middle East",
      "title_contains": ["History of the Middle East"],
      "title_regex": null
    }
  ]
}
```

### Phase 5: Creator Tracking and Queue

Completed.

Implemented:

- Creator source registry: `library/_creators.json`.
- `creator add`.
- `creator list`.
- `creator fetch`.
- `creator enqueue`.
- Queue file: `library/_queue.json`.
- `queue status`.
- `queue list`.
- `queue run`.

Queue jobs run through the same `process_video()` pipeline as a manually supplied video URL.

### Phase 6: Desktop UI

Completed as MVP.

Implemented a local web UI served by ClipVault itself:

- Video tab: paste URL, choose model/device, optional series, force, keep audio, view logs and result.
- Library tab: browse platform/creator/series/video tree, read transcript, open output folder.
- Creator tab: add creators, fetch recent videos, enqueue new videos.
- Queue tab: inspect jobs, remove jobs, run jobs, stream logs.
- Settings tab: save library path, ASR model/device, cookies path.

The UI is local-only and uses a random token. The server binds to `127.0.0.1`.

## Project Structure

### Root Files

```text
pyproject.toml
```

Project metadata, dependencies, package discovery, and CLI entry point:

```text
clipvault = "clipvault.cli:main"
```

```text
requirements.lock
requirements-gpu-win.lock
uv.lock
```

Pinned dependency files. GPU runtime is intentionally separate because Windows NVIDIA wheels are large.

```text
clipvault.ps1
```

Windows launcher for local development.

```text
README.md
```

User-facing quick start, command examples, login notes, output layout, and common workflows.

```text
AGENTS.md
```

Development rules for future agents and contributors: stepwise development, development logs, program logs, validation samples, and open-source maintenance expectations.

```text
DESIGN.md
```

UI design guidance for the desktop web interface.

```text
.gitignore
```

Ignores local runtime state such as `.venv/`, `.tmp/`, `library/`, `.secrets/`, `.claude/`, caches, and generated cookie files.

### Python Package

```text
clipvault/cli.py
```

Main CLI entry point and orchestration. Defines top-level commands:

- `video`
- `library`
- `creator`
- `queue`
- `auth`
- `ui`

It also contains `process_video()`, the core end-to-end video pipeline.

```text
clipvault/platforms.py
```

Platform detection, language preferences, and `yt-dlp` metadata extraction.

```text
clipvault/adapters.py
```

Platform adapter boundary for normalizing flat playlist/channel entries into usable video URLs. Covers Bilibili, YouTube, and Douyin URL shaping.

```text
clipvault/subtitles.py
```

Subtitle selection and parsing:

- Bilibili JSON.
- YouTube JSON3.
- VTT.
- SRT.

`get_platform_subtitles()` applies platform language priority and returns segments plus a source descriptor such as `subtitle:en:json3` or `automatic_caption:en-orig:json3`.

```text
clipvault/asr.py
```

Local ASR through `faster-whisper`. Resolves device and compute type, uses local cached models, and returns transcript segments.

```text
clipvault/exporters.py
```

Converts transcript segments into:

- SRT.
- Plain text.
- Markdown.

```text
clipvault/library.py
```

Library path generation, manifest helpers, cache completion checks, creator/series indexes, and index rebuild logic.

```text
clipvault/series_rules.py
```

Title-based series assignment rules. Manual `--series` takes priority over rules.

```text
clipvault/creators.py
```

Creator registry, fetch preview, processed/new status detection, queue creation, queue listing, and queue persistence.

```text
clipvault/auth.py
clipvault/login.py
clipvault/credentials.py
```

Credential handling:

- Bilibili QR login.
- Stored credentials in `%APPDATA%\clipvault\auth.toml`.
- Conversion to temporary Netscape cookies for `yt-dlp`.
- Auth listing and logout.

```text
clipvault/models.py
clipvault/text.py
```

Small shared data structures and text helpers.

### UI Package

```text
clipvault/ui/server.py
```

Local HTTP server for the desktop UI. Uses `ThreadingHTTPServer`, binds to `127.0.0.1`, and protects write/read APIs with a random token.

Important API routes:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/status` | Health/version check |
| GET | `/api/settings` | Load UI settings |
| POST | `/api/settings` | Save UI settings |
| POST | `/api/video` | Start a video processing job |
| GET | `/api/process/status` | Get current job status |
| GET | `/api/process/events` | SSE stream for job logs/results |
| POST | `/api/process/stop` | Stop current job |
| GET | `/api/library` | Read library tree |
| GET | `/api/library/transcript` | Read transcript content |
| GET | `/api/library/video` | Read manifest/transcript details |
| POST | `/api/library/rebuild-index` | Rebuild indexes |
| POST | `/api/open-path` | Open output folder, restricted to library root |
| GET | `/api/creators` | List creators |
| POST | `/api/creators/add` | Add creator source |
| POST | `/api/creators/fetch` | Fetch recent creator videos |
| POST | `/api/creators/enqueue` | Enqueue creator videos |
| GET | `/api/queue` | Read queue status/jobs |
| POST | `/api/queue/remove` | Remove queue job |
| POST | `/api/queue/run` | Run queue jobs |

```text
clipvault/ui/static/index.html
clipvault/ui/static/app.js
clipvault/ui/static/style.css
```

Frontend UI files. They are intentionally simple static files with no build step.

### Docs and Logs

```text
docs/plan/roadmap.md
```

Main project roadmap and phase history.

```text
docs/plan/phase6-ui-spec.md
```

Desktop UI implementation spec, including local security boundaries and job model.

```text
logs/development/
```

Development logs by step. These document what changed, why, and how it was verified.

```text
logs/program/
```

Program log conventions, so user-visible runtime messages stay consistent.

### Tests

```text
tests/
```

Unit and integration-style tests for:

- Platform detection and adapters.
- Subtitle parsing.
- Exporters.
- Library helpers and index rebuild.
- Series rules.
- Creator registry/fetch/enqueue.
- Queue execution.
- Auth and login behavior.
- CLI argument parsing.
- UI server helper behavior.

Current full suite result at MVP review time:

```text
271 passed
```

## CLI Surface

### Single Video

```powershell
clipvault video <url>
clipvault video <url> --series "Series Name"
clipvault video <url> --force
clipvault video <url> --device cuda --model small
clipvault video <url> --cookies
clipvault video <url> --cookies ".secrets\cookies.txt"
```

Legacy shorthand is supported:

```powershell
clipvault <url>
```

### Library

```powershell
clipvault library rebuild-index
clipvault library rebuild-index --library "E:\VideoSubs"
clipvault library rebuild-index --dry-run
```

### Creator

```powershell
clipvault creator add <creator-url> --name "Display Name"
clipvault creator list
clipvault creator fetch <creator-id-or-name> --limit 20
clipvault creator enqueue <creator-id-or-name> --limit 20
```

### Queue

```powershell
clipvault queue status
clipvault queue list
clipvault queue list --status pending
clipvault queue run --limit 1
clipvault queue run --limit 3 --retry-failed
```

### Auth

```powershell
clipvault auth login
clipvault auth list
clipvault auth logout
```

### UI

```powershell
clipvault ui
clipvault ui --port 8080
clipvault ui --no-open
clipvault ui --library "E:\VideoSubs"
```

## Data Files

### Video Manifest

Each processed video has:

```text
manifest.json
```

Important fields:

- `schema_version`
- `platform`
- `source_url`
- `webpage_url`
- `video_id`
- `title`
- `uploader`
- `creator_id`
- `duration`
- `upload_date`
- `processed_at`
- `series`
- `subtitle_source`
- `asr_model`
- `asr_device`
- `output_files`

### Creator Index

```text
library/<platform>/<creator>/_index.json
```

Used by library browsing and future GUI/automation features.

### Series Index

```text
library/<platform>/<creator>/<series>/_index.json
```

Created only for series folders.

### Creator Registry

```text
library/_creators.json
```

Tracks followed creators/channels.

### Queue

```text
library/_queue.json
```

Tracks pending/done/failed transcript jobs.

### UI Settings

Windows:

```text
%APPDATA%\ClipVault\settings.json
```

Other systems:

```text
~/.config/ClipVault/settings.json
```

Stores:

- `library`
- `model`
- `device`
- `compute_type`
- `cookies`

### Credentials

Stored auth:

```text
%APPDATA%\clipvault\auth.toml
```

Generated local Netscape cookies cache:

```text
%APPDATA%\clipvault\netscape_cookies.txt
```

These files are local secrets and must never be committed.

## Runtime Behavior

The single-video pipeline is:

```text
URL
  -> yt-dlp metadata
  -> platform detection
  -> series resolution
  -> cache check
  -> platform subtitle/automatic caption lookup
  -> ASR fallback if no subtitle
  -> srt/txt/md export
  -> manifest update
  -> creator/series index update
```

The UI does not duplicate pipeline logic. It launches CLI subprocess jobs and streams logs/results through SSE.

## Manual Validation State

### YouTube

Validated:

```text
https://www.youtube.com/watch?v=Vdd6EOlRVbg
```

Result:

- Platform: `youtube`
- Creator: `Jabzy`
- Series: `History of the Middle East`
- Source: `automatic_caption:en-orig:json3`
- Segments: `983`
- Cache hit also returns `source` and `segments`

### Bilibili

Validated:

```text
https://www.bilibili.com/video/BV16G411973A
```

Result:

- Platform: `bilibili`
- Creator: `一条闲木鱼`
- Series: `大明王朝`
- Source: `asr:faster-whisper`
- Model/device: `small` + `cuda`
- Segments: `1290`
- Stored Bilibili credentials work with `--cookies`

### Douyin

Attempted but not stable:

```text
https://www.douyin.com/video/7609585779190612002
```

Result:

- `yt-dlp` returned `Fresh cookies are needed`.
- Current stored credentials only include Bilibili.
- Douyin should stay marked as experimental until a reliable cookie/login/export path is defined.

## Known Limitations

- Douyin extraction is not stable yet.
- The UI model selector can expose models that are not locally cached; missing models fail clearly, but the UI does not yet show installed model status.
- Series rules are manually edited JSON files; there is no UI or CLI management command yet.
- Creator tracking relies on platform extractor behavior and may change when platforms change their pages.
- The UI is functional but still MVP-level; it needs sustained real-user testing.
- No AI note generation, Q&A, retrieval, or knowledge-base layer has been implemented yet.

## Future Development Direction

### Near Term: Product Hardening

1. Use the app heavily with real videos and record UX issues.
2. Add a structured issue table in `docs/plan/` after real usage.
3. Improve UI error display and empty states.
4. Show installed ASR models and prevent selecting unavailable models.
5. Add UI controls for series rules.
6. Improve queue history, retry visibility, and failed-job diagnostics.

### Platform Reliability

1. Harden Bilibili login/session refresh and subtitle detection.
2. Keep YouTube validation stable with fixed sample videos.
3. Research Douyin cookies and extractor feasibility before claiming support.
4. Add platform-specific notes for common failure modes.

### Library Management

1. Better search/filter across local transcripts.
2. Rename/move series from UI.
3. Duplicate detection and cleanup tools.
4. Import/export library metadata.
5. Optional migration helpers for old layouts.

### AI Layer

Only after transcript acquisition and library browsing are stable:

1. Transcript chunking.
2. Local or API-based summarization.
3. Markdown note generation.
4. Q&A over one transcript.
5. Q&A over a creator/series collection.
6. Claim extraction and fact-checking workflows.

The core principle should remain: transcripts are the durable source asset; AI notes are derived artifacts.

## Handoff Notes

For a new developer, start with:

1. `README.md` for usage.
2. `docs/plan/roadmap.md` for phased context.
3. `clipvault/cli.py::process_video()` for the main pipeline.
4. `clipvault/library.py` for storage, cache, and indexes.
5. `clipvault/ui/server.py` for local API and job execution.
6. `tests/test_cli.py`, `tests/test_library.py`, and `tests/test_ui_server.py` for behavioral contracts.

Before making changes:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check clipvault\ui\static\app.js
git diff --check
```

For real-link validation, use the samples listed in `docs/plan/roadmap.md` and record the exact URL, result, source, segment count, and failure mode.
