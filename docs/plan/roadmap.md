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

Planned work:

- Add manual series assignment:
  - `--series "Series Name"`.
- Library path with series:
  - `library/<platform>/<creator>/<series>/<video title - id>/`
- Add title-rule based auto-assignment later:
  - keyword rules.
  - regex rules.
- Add creator-level index files:
  - videos processed.
  - known series.
  - latest processed item.
- Add basic import of historical transcript files only after current library schema is stable.

Success criteria:

- A user can group videos from the same creator into a named series.
- Future creator subscriptions can build on the same metadata.

## Phase 5: Creator Tracking and Batch Ingestion

Goal: support following creators and collecting new videos.

Planned work:

- Add creator/channel source records.
- Add commands:
  - `clipvault creator add <url>`.
  - `clipvault creator list`.
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
3. Add manual `--series` support only after the platform/cache boundary is stable.
4. Add creator-level index design under `docs/plan/` before implementing subscriptions.
5. Keep GUI and AI note generation out of scope until transcript acquisition is dependable.
