# 2026-05-04: Project Init and Roadmap

## Target

Initialize ClipVault project structure, align on development roadmap, and begin
Phase 1 (Stabilize Transcript Core).

## Steps

1. Established project scaffolding:
   - `pyproject.toml` with setuptools build.
   - `clipvault/` package with CLI entrypoint.
   - `requirements.lock` and `requirements-gpu-win.lock` for pinned deps.
   - `uv.lock` for uv-based dependency management.
   - Windows launcher `clipvault.ps1`.
2. Split core logic into modules:
   - `cli.py`, `platforms.py`, `subtitles.py`, `asr.py`
   - `library.py`, `exporters.py`, `models.py`, `text.py`
3. Created development artifacts:
   - `AGENTS.md` — developer guide for future contributors.
   - `docs/plan/roadmap.md` — 6-phase development roadmap.
   - `logs/development/` and `logs/program/` directories.
4. Verified Bilibili flow end-to-end:
   - BV1fX4y1Q7Ux processed successfully via platform subtitles.
5. Out-of-scope decisions recorded:
   - AI note generation deferred until transcript library is stable.
   - GUI deferred until core pipeline and library management are stable.

## Changes

- Initial commit: all scaffolding, modules, and launcher.
- Split transcript pipeline modules from monolithic prototype.
- Created roadmap and agent documentation.

## Verification

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV1fX4y1Q7Ux" --force
# Output: status=ok, source=subtitle:zh-CN:json3
```

## Follow-ups

1. Add tests for subtitle parsers and exporters (task #2).
2. Add program logging to CLI pipeline (task #3).
3. Add schema_version and processing metadata to manifest.json (task #4).
4. Improve error messages (task #5).
5. Validate YouTube support (task #6).

---

## 2026-05-04: Phase 1 Tasks 2-6

### Task 2 – Unit Tests

Added test suite with 49 tests across 3 files:

- `tests/test_subtitles.py` (22 tests): Bilibili JSON, YouTube JSON3, VTT, SRT
  parsing, language priority, extension ranking, dispatch logic.
- `tests/test_exporters.py` (10 tests): SRT/plain-text/Markdown formatting,
  edge cases (empty segments, multi-line, clock format with/without hours).
- `tests/test_library.py` (17 tests): platform guessing, safe_name,
  first_text, write_json, update_manifest, build_manifest schema.

All 49 tests pass.

### Task 3 – Program Logging

Added `[pipeline]`, `[metadata]`, `[subtitle]`, `[audio]`, `[export]` log
calls to stderr across cli.py, platforms.py, subtitles.py. ASR module already
had `[asr]` logging from baseline.

### Task 4 – Manifest Schema

- Added `schema_version` (1), `processed_at`, `platform`,
  `subtitle_source`, `asr_model`, `asr_device`, `output_files`,
  `creator_id`, `source_url` to `build_manifest`.
- Added `guess_platform()` for URL-based platform detection (bilibili,
  youtube, douyin, unknown).
- Added `update_manifest()` for post-processing enrichment (subtitle
  source, ASR metadata, output file list).

### Task 5 – Error Messages

- `platforms.py`: Wrapped yt-dlp failures with actionable guidance
  (check URL/network, update yt-dlp). Added ffmpeg hint to audio
  download error.
- `asr.py`: Model-missing detection with download instructions.
  Empty-transcript error with possible causes. Cache-miss log message.

### Task 6 – YouTube Validation

Tested with `dQw4w9WgXcQ`:
- Platform detection: `platform: "youtube"` correctly identified.
- Subtitles: 61 segments from `subtitle:en:json3` (YouTube JSON3 format).
- Full pipeline: metadata → subtitle extraction → 3 output files → manifest.
- Manifest: `creator_id` populated, `subtitle_source` recorded, schema v1.

No code changes needed — YouTube works out of the box through the existing
yt-dlp path.

### Files Changed

- `tests/__init__.py` — new
- `tests/test_subtitles.py` — new
- `tests/test_exporters.py` — new
- `tests/test_library.py` — new
- `clipvault/cli.py` — logging, manifest update after processing
- `clipvault/platforms.py` — logging, error messages
- `clipvault/subtitles.py` — logging
- `clipvault/asr.py` — error messages, model cache log
- `clipvault/library.py` — schema v1, platform detection, update_manifest

