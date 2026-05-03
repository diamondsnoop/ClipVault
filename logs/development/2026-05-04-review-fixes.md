# 2026-05-04: Review Fixes After Phase 1/2

## Target

Fix the three issues found during review of Phase 1 and Phase 2:

1. Cache completion state was too loose.
2. ASR model guidance implied behavior that the code did not implement.
3. Documentation still described the old project path and old library layout.

## Steps

### Step 1 - Cache Completion

Changed `is_completed()` so a v1 manifest is considered complete only when:

- `subtitle_source` is populated.
- `output_files` is a non-empty list.
- Every listed output file exists under the video directory.

Legacy v0 compatibility remains: old manifests without `subtitle_source` are accepted only if `transcript.srt`, `transcript.txt`, and `transcript.md` all exist.

Added and adjusted tests for complete and incomplete manifest output states.

### Step 2 - Runtime Logging and ASR Guidance

Added a `[cache] hit` program log when the CLI reuses a completed cache entry.

Updated ASR missing-model messaging to match current behavior: ClipVault uses `local_files_only=True`, so users must pre-download a faster-whisper model into the Hugging Face cache or pass a local model directory with `--model`.

### Step 3 - Documentation Alignment

Updated:

- `README.md`
- `AGENTS.md`
- `docs/plan/roadmap.md`

The docs now describe the current Phase 2 library layout:

```text
library/<platform>/<creator>/<video title - id>/
```

They also document legacy cache compatibility and the local-only ASR model assumption.

## Changes

- `clipvault/library.py`
- `clipvault/asr.py`
- `clipvault/cli.py`
- `tests/test_library.py`
- `README.md`
- `AGENTS.md`
- `docs/plan/roadmap.md`

## Verification

Completed:

- `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp="E:\myproject\ClipVault\review-pytest-tmp"`
  - Result: 64 passed.
- `.\clipvault.ps1 --help`
  - Result: help text displayed normally.
- `.\.venv\Scripts\python.exe -m pip check`
  - Result: no broken requirements found.
- `.\.venv\Scripts\python.exe -m compileall -q clipvault tests`
  - Result: passed.
- Cached Bilibili run:
  - URL: `https://www.bilibili.com/video/BV1fX4y1Q7Ux`
  - Result: `status=cached`, platform-aware `library/bilibili/...` path returned, `[cache] hit` log displayed.
- `git diff --check`
  - Result: passed, with Windows LF-to-CRLF notices only.

## Follow-ups

- Consider adding a small documented command for pre-downloading faster-whisper models.
- Add platform adapter boundaries before implementing Douyin-specific extraction behavior.
- Keep future cache changes covered by tests that remove one output file and expect a reprocess.
- Use the documented manual validation samples for platform work:
  - Bilibili: 马督公《睡前消息》系列.
  - YouTube: Jabzy, `History of the Middle East` series.
  - Douyin: 王朝董事会《大明王朝》系列.
