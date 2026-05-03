# 2026-05-04: Phase 4 Step 1 — Manual Series Library Grouping

## Target

Add a `--series` CLI parameter so that users can group videos from the same
creator into a named series folder. The series is manually assigned per video;
no auto-detection, no creator subscriptions.

## Steps

1. **`library.py`** — Add `series: str | None = None` to:
   - `video_directory()` — inserts series segment between creator and video.
   - `resolve_video_directory()` — when series is provided, only checks/returns
     the series path (never falls back to a non-series path).
   - `build_manifest()` — writes `"series": <series>` (or `null`).

2. **`cli.py`** — Add `--series SERIES` argument. Pass `series` through
   `process_video()` to path and manifest builders. Print `[library] series: ...`
   when set.

3. **Tests** (10 new tests, 95 total):
   - `test_video_directory_with_series` — path includes series segment.
   - `test_video_directory_series_sanitized` — special chars cleaned.
   - `test_video_directory_series_none_is_unchanged` — explicit None == omit.
   - `test_build_manifest_series` — manifest has series field.
   - `test_build_manifest_series_none` — series is None when omitted.
   - `test_resolve_with_series_returns_series_path` — series requested, non-series
     cache exists → returns series path (not non-series).
   - `test_resolve_with_series_hits_series_cache` — series cache hit works.
   - `test_resolve_no_series_still_hits_non_series_cache` — no-regression.
   - `test_process_video_with_series` — mocked integration test.
   - `test_process_video_without_series` — series is null in manifest.

4. **Documentation** — Updated README.md, AGENTS.md, docs/plan/roadmap.md.

5. **Smoke test** — Ran against `jNQXAC9IVRw` (Me at the zoo) with
   `--series "Test Series"`:
   - Output: `library/youtube/jawed/Test Series/Me at the zoo - jNQXAC9IVRw/`.
   - Manifest: `"series": "Test Series"`.
   - Boundary verified: same URL without `--series` did NOT hit the series cache
     (reprocessed to `library/youtube/jawed/...`).

## Changes

- `clipvault/library.py` — series parameter in 3 functions
- `clipvault/cli.py` — `--series` arg, pipeline integration, log
- `tests/test_library.py` — 8 new series tests
- `tests/test_cli.py` — 2 new integration tests (mocked)
- `README.md` — series in output layout and examples
- `AGENTS.md` — series in capabilities and commands
- `docs/plan/roadmap.md` — Phase 4 Step 1 marked done

## Verification

```
pytest -q                              # 95 passed
clipvault --help                        # --series SERIES shown
pip check                               # no broken deps
compileall -q clipvault tests           # clean
git diff --check                        # no whitespace errors
```

## Follow-ups

- **Creator index** — after manual series is stable, add per-creator index
  files listing known series and latest processed video.
- **Series auto-rules** — keyword/regex rules to auto-assign series by title
  pattern. Keep this optional and opt-in.
- **Historical migration** — add a one-shot command to retroactively assign
  series to already-processed videos. Not needed for Phase 4 Step 1.
