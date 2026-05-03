# 2026-05-04: Phase 4 Core — Creator and Series Indexes

## Target

Auto-maintain local JSON indexes so the library is self-describing without a
separate indexing pass. Creator indexes track all videos per creator; series
indexes track videos in a named series.

## Design

Two index files are maintained automatically after every completed pipeline run
(both new processing and cache hits):

### Creator index
`library/<platform>/<creator>/_index.json`

```json
{
  "schema_version": 1,
  "type": "creator",
  "platform": "youtube",
  "creator": "Jabzy",
  "updated_at": "...",
  "series": [
    { "name": "History of the Middle East", "video_count": 3, "latest_processed_at": "..." }
  ],
  "videos": [
    {
      "video_id": "...",
      "title": "...",
      "series": "History of the Middle East",
      "relative_path": "History of the Middle East/Title - id",
      "source_url": "...",
      "subtitle_source": "...",
      "duration": 123,
      "upload_date": "...",
      "processed_at": "..."
    }
  ]
}
```

### Series index (only when `--series` is used)
`library/<platform>/<creator>/<series>/_index.json`

```json
{
  "schema_version": 1,
  "type": "series",
  "platform": "youtube",
  "creator": "Jabzy",
  "series": "History of the Middle East",
  "updated_at": "...",
  "video_count": 1,
  "videos": [
    {
      "video_id": "...",
      "title": "...",
      "relative_path": "Title - id",
      "source_url": "...",
      "subtitle_source": "...",
      "duration": 123,
      "upload_date": "...",
      "processed_at": "..."
    }
  ]
}
```

Key design decisions:

- **Deduplication**: Videos keyed by `video_id`; re-processing overwrites, not appends.
- **Sorting**: `processed_at` descending, title ascending as tiebreaker.
- **Relative paths**: Never absolute, so indexes survive library relocation.
- **Blank series**: `normalize_series()` converts whitespace-only to `None`; no series index created.
- **Cache hit**: Indexes are re-generated on cache hit, so pre-index caches get indexed on first access.
- **Non-blocking**: Index update failures are silently caught; the pipeline result is unaffected.

## Steps

1. Added `creator_index_path()`, `series_index_path()`, `_load_json()`,
   `_video_entry()`, and `update_library_indexes()` to `library.py`.

2. `cli.py` — imported `update_library_indexes`, called it after:
   - New processing (after manifest is finalized via `update_manifest`).
   - Cache hit (reads existing manifest from disk).

3. Tests (13 new, 116 total):
   - **Path helpers**: `test_creator_index_path`, `test_series_index_path`,
     `test_series_index_path_none`.
   - **Creator index**: creation without series, with series, dedup, no absolute paths.
   - **Series index**: creation, not created without series, not created for blank series,
     video count, stripped series name.
   - **Cache hit**: `test_process_video_cache_hit_creates_index` — removes indexes,
     runs cached, verifies re-creation.

4. Documentation — Updated README.md, AGENTS.md, docs/plan/roadmap.md.

5. Smoke test — Ran against `jNQXAC9IVRw` with `--series "Test Series"`:
   - `[index] creator: .../library/youtube/jawed/_index.json`
   - `[index] series: .../library/youtube/jawed/Test Series/_index.json`
   - Both indexes contain correct video entry with relative paths.
   - Cache hit (indexes deleted first) correctly recreated both indexes.

## Changes

- `clipvault/library.py` — 5 new functions, `INDEX_SCHEMA_VERSION`
- `clipvault/cli.py` — import and call `update_library_indexes` in both paths
- `tests/test_library.py` — 11 new index tests
- `tests/test_cli.py` — 2 new index tests (cache hit + series dedup)
- `README.md` — index layout and description
- `AGENTS.md` — index capabilities
- `docs/plan/roadmap.md` — Phase 4 Step 2 marked done

## Verification

```
pytest -q                              # 116 passed
clipvault --help                        # --series SERIES shown
pip check                               # no broken deps
compileall -q clipvault tests           # clean
git diff --check                        # no whitespace errors
```

## Follow-ups

- **Auto series rules** — keyword/regex rules to auto-assign series by title
  pattern. Keep this optional and opt-in. Not done in this step.
- **Creator subscription** — follow creators and batch-fetch new videos.
  Requires the index foundation from this step. Not done here.
- **Historical migration** — one-shot command to retroactively create indexes
  for already-processed videos. Not done in this step — cache-hit indexing
  handles it incrementally.

## Review Fixes (2026-05-04)

Three issues found during Phase 4 Core review, fixed before commit.

### Issue 1: Silent index failure

**Problem**: Both index update paths in `cli.py` used `except Exception: pass`,
silently swallowing index failures. Index is Phase 4 Core's primary feature;
failures must be visible without blocking the pipeline.

**Fix**: Replaced `pass` with error logging:
- Cache hit: `[index] failed on cache hit ({video_dir}): {exc}`
- New processing: `[index] failed ({video_dir}): {exc}`

### Issue 2: null series in creator index aggregation

**Problem**: `update_library_indexes()` included `None`-keyed entries in the
series aggregation, producing `{"name": null, "video_count": ...}` in the
creator index's `series` array.

**Fix**: The aggregation loop now skips entries where
`normalize_series(v.get("series"))` is falsy. Unassigned videos remain in
`videos[]` with `series: null` but do not appear in `series[]`.

### Issue 3: Sort order inconsistency

**Problem**: `sort(..., reverse=True)` made both `processed_at` and `title`
descending, but the design doc specifies `processed_at` descending and `title`
ascending.

**Fix**: Changed from single-pass `reverse=True` to two-pass stable sort:

```python
videos.sort(key=lambda v: v.get("title") or "")       # title ascending
videos.sort(key=lambda v: v.get("processed_at") or "", reverse=True)  # processed_at desc
```

### New tests (4 added, 120 total)

- `test_creator_index_no_series_agg_empty` — series list is `[]` when no
  videos have series
- `test_creator_index_mixed_series_agg` — null series not in aggregation
- `test_creator_index_sort_order` — same `processed_at`, different titles:
  title ascending confirmed
- `test_series_index_sort_order` — same sort order in series index

### Verification

```
pytest -q                              # 120 passed
pip check                               # no broken deps
compileall -q clipvault tests           # clean
git diff --check                        # no whitespace errors
```
