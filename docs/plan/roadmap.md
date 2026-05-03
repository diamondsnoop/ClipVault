# ClipVault Roadmap

## Product Direction

ClipVault is a local-first video transcript vault. Its core value is reliable acquisition, storage, and long-term maintenance of original video content transcripts.

The project should not become a generic AI note generator in the near term. AI summaries, Q&A, and note generation can be added later, but only after transcript acquisition and library management are stable.

## Current Baseline

Implemented as of the current baseline:

- CLI command: `clipvault`.
- Windows launcher: `clipvault.ps1`.
- Bilibili URL processing through `yt-dlp`.
- YouTube subtitle pipeline validation through the generic `yt-dlp` path.
- Platform subtitles/automatic captions when available.
- Audio download fallback when subtitles are unavailable.
- Local ASR through `faster-whisper`.
- CUDA auto-selection with CPU fallback.
- Unit tests for subtitle parsing, exporters, and library helpers.
- User-visible stderr logs for pipeline stages.
- Outputs:
  - `manifest.json`
  - `transcript.srt`
  - `transcript.txt`
  - `transcript.md`
- Current library layout:
  - `library/<platform>/<creator>/<video title - id>/`
- Legacy cache compatibility:
  - `library/<creator>/<video title - id>/`
- Dependency split:
  - `requirements.lock` for base dependencies.
  - `requirements-gpu-win.lock` for optional Windows NVIDIA GPU runtime.
- Core code split into modules:
  - `cli.py`
  - `platforms.py`
  - `subtitles.py`
  - `asr.py`
  - `library.py`
  - `exporters.py`
  - `models.py`
  - `text.py`

## Development Principles

- Build from transcript acquisition outward.
- Treat original transcripts as the primary asset.
- Keep generated notes and AI summaries out of scope until the transcript library is solid.
- Prefer local-first storage and open file formats.
- Keep GPU dependencies optional.
- Make runtime behavior observable through program logs.
- Record meaningful development steps in `logs/development/`.
- Keep the project friendly to future open source contributors.
- Treat cache entries as complete only when manifest state and actual output files agree.
- Keep ASR model behavior explicit: local-only unless automatic model download is intentionally added.

## Manual Validation Samples

Use these samples for manual and integration-style checks when validating platform behavior. They are intentionally not part of the default unit test suite because external platform content, subtitles, and access rules can change.

- Bilibili: 马督公《睡前消息》系列.
- YouTube: Jabzy, `History of the Middle East` series.
- Douyin: 王朝董事会《大明王朝》系列.

For each manual validation, log the exact URL, date, transcript source, output path, and failure mode if any.

## Phase 1: Stabilize Transcript Core

Goal: make the existing transcript pipeline reliable, testable, and maintainable.

Status: completed in commit `e2e571c`, with follow-up review fixes after Phase 2.

Planned work:

- Add unit tests for subtitle parsing:
  - Bilibili JSON subtitles.
  - YouTube JSON3 captions.
  - VTT.
  - SRT.
- Add tests for exporters:
  - `to_srt`.
  - `to_plain_text`.
  - `to_markdown`.
- Add program logging:
  - Metadata extraction start/success/failure.
  - Subtitle discovery result.
  - Audio download start/success/failure.
  - ASR start/success/failure.
  - CUDA fallback.
  - Export paths.
- Improve error messages:
  - Missing `ffmpeg`.
  - Unsupported/failed URL extraction.
  - No subtitles and audio download failure.
  - ASR model missing.
- Add a stable `manifest.json` schema version.

Success criteria:

- Existing Bilibili flow still works.
- Test suite covers subtitle parsing/export formatting.
- Users can understand which stage is running and why a failure happened.

## Phase 2: Library Structure and Metadata

Goal: make ClipVault a maintainable transcript library instead of a one-off output script.

Status: completed in commit `650235b`, with follow-up cache/documentation fixes after review.

Planned work:

- Introduce a more future-proof library layout:
  - `library/<platform>/<creator>/<video title - id>/`
- Preserve backward compatibility or provide a migration plan for the current layout:
  - `library/<creator>/<video title - id>/`
- Expand `manifest.json`:
  - `schema_version`.
  - `platform`.
  - `source_url`.
  - `webpage_url`.
  - `video_id`.
  - `title`.
  - `creator_name`.
  - `creator_id` when available.
  - `duration`.
  - `upload_date`.
  - `processed_at`.
  - `subtitle_source`.
  - `asr_model`.
  - `asr_device`.
  - `output_files`.
- Add cache/reuse behavior based on manifest state, not only `transcript.md`.
- Verify output files listed by manifest before treating a cache entry as complete.

Success criteria:

- New outputs have platform-aware paths.
- Manifest contains enough metadata for future series and creator management.
- Existing cached videos remain usable.

## Phase 3: Multi-Platform Transcript Support

Goal: support mainstream video platforms through the same transcript pipeline.

Priority order:

1. Bilibili hardening.
2. YouTube validation.
3. Douyin research/prototype.

Planned work:

- Add platform identification around `yt-dlp` metadata.
- Validate YouTube:
  - Manual subtitles.
  - Automatic captions.
  - Audio fallback.
- Keep platform-specific hacks isolated in platform modules.
- Do not overcommit to Douyin quality until extraction reliability is proven.

Success criteria:

- Bilibili and YouTube can both produce transcript outputs through the same CLI.
- Platform name is recorded in manifest and library path.
- Douyin support has a documented feasibility result before being treated as stable.

## Phase 4: Series and Creator Organization

Goal: support long-term maintenance around creators and recurring series.

### Phase 4 Step 1 — Manual Series Assignment (completed)

Added `--series "Series Name"` CLI parameter. The library path with series:

```text
library/<platform>/<creator>/<series>/<video title - id>/
```

Manifest includes `"series": "Series Name"` when assigned. Cache boundary is strict: a `--series` run will never hit a non-series cache entry.

### Phase 4 Step 2 — Creator and Series Indexes (completed)

Auto-maintained JSON indexes for library browsing:

- **Creator index** at `library/<platform>/<creator>/_index.json` — lists all videos and aggregates known series.
- **Series index** at `library/<platform>/<creator>/<series>/_index.json` — created only when `--series` was used.
- Indexes are plain JSON, updated on both new processing and cache hits.
- Videos deduplicated by `video_id`; sorted by `processed_at` descending, title ascending.
- Relative paths only, so indexes survive library relocation.

### Phase 4 Step 3 — Title-based Auto Series Rules (completed)

Optional title-matching rules to auto-assign series when `--series` is not passed:

- Rule file at `library/<platform>/<creator>/_series_rules.json` (per creator).
- Supports `title_contains` (keyword list) and `title_regex` (optional regex).
- First matching rule wins; rules evaluated in file order.
- Explicit `--series` always takes priority over auto-rules.
- Missing or invalid rule file is non-blocking (logged, not crashed).
- Implemented in a new `clipvault/series_rules.py` module.

### Phase 4 Step 4 — Library Index Rebuild (completed)

Maintenance command for recovering index state from existing local manifests:

```powershell
clipvault library rebuild-index
clipvault library rebuild-index --library "E:\VideoSubs"
clipvault library rebuild-index --library "E:\VideoSubs" --dry-run
```

- Scans completed `manifest.json` entries under the library.
- Rebuilds creator and series `_index.json` files from scratch.
- Removes stale index files and stale video entries when manifests disappear.
- Skips invalid or incomplete manifests with `[index] skipped manifest (...)` logs.
- Does not download videos, fetch subtitles, or run ASR.

Success criteria:

- A user can group videos from the same creator into a named series. ✅
- Future creator subscriptions can build on the same metadata. ✅ (index foundation) ✅
- Series can be auto-assigned by title pattern without requiring `--series`. ✅
- Indexes can be rebuilt from disk if they become stale. ✅

## Phase 5: Creator Tracking and Batch Ingestion

Goal: support following creators and collecting new videos.

### Phase 5 Step 1 — Creator Source Registry (completed)

Local registry for creator/channel sources:

```powershell
clipvault creator add <url> --name "Display Name"
clipvault creator list
```

- Stores records in `library/_creators.json`.
- Records platform, display name, source URL, added time, and check state.
- Adding the same source URL is idempotent and updates the display name.
- This step does not fetch recent videos yet.

Planned work:

- ~~Add creator/channel source records.~~
- Add commands:
  - ~~`clipvault creator add <url>`.~~
  - ~~`clipvault creator list`.~~
  - `clipvault creator fetch <creator>`.
- Fetch recent videos from a creator/channel.
- Skip already processed videos.
- Queue transcript jobs.
- Report per-video status.

Success criteria:

- A followed creator can be checked for new videos.
- New videos can be ingested without manually pasting each video URL.

## Phase 6: Desktop UI

Goal: make ClipVault usable without command-line knowledge.

Do this only after the core library and metadata model are stable.

Initial UI should support:

- Add video URL.
- Show processing stage and logs.
- Browse library by platform/creator/series.
- Open transcript Markdown or output folder.
- Configure library path, ASR model, and device.

Success criteria:

- GUI is a thin shell over the stable core pipeline.
- CLI remains fully supported.

## Out of Scope Until Later

- AI note generation.
- Chat/Q&A over transcripts.
- Cloud sync.
- Mobile app.
- Full Douyin reliability claims.
- Automatic factual verification.

These may be revisited only after the transcript vault itself is dependable.

## Immediate Next Tasks

1. Add focused Bilibili hardening tests and real-link regression notes.
2. Define a small platform adapter interface before adding Douyin-specific logic.
3. ~~Add manual `--series` support only after the platform/cache boundary is stable.~~ (done)
4. ~~Add creator-level index design under `docs/plan/` before implementing subscriptions.~~ (done)
5. ~~Add title-based auto series rules.~~ (done)
6. Keep GUI and AI note generation out of scope until transcript acquisition is dependable.
