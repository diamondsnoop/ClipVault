# 2026-05-04: Phase 4 Step 4 — Library Index Rebuild

## Target

Add a local maintenance command that can rebuild creator and series indexes
from existing completed `manifest.json` entries.

This step keeps ClipVault focused on transcript library maintenance. It does
not download videos, fetch subtitles, run ASR, or change the video processing
pipeline.

## Steps

1. Reviewed `AGENTS.md`, `docs/plan/roadmap.md`, `clipvault/cli.py`, and
   `clipvault/library.py`.
2. Added full-index rebuild helpers in `library.py`.
3. Added `clipvault library rebuild-index` and `--dry-run` in `cli.py`.
4. Added focused tests for empty libraries, mixed series, multiple platforms,
   stale index cleanup, bad manifests, deduplication, and dry-run behavior.
5. Updated README, roadmap, and agent guidance.

## Changes

- `clipvault/library.py`
  - Added `rebuild_library_indexes()`.
  - Added scan-time validation for completed manifests.
  - Added stale `_index.json` removal.
  - Added `video_id` deduplication for full rebuilds.
- `clipvault/cli.py`
  - Added `clipvault library rebuild-index`.
  - Kept the existing `clipvault <url>` flow unchanged.
- `tests/test_library.py`
  - Added rebuild coverage for creator and series indexes.
- `tests/test_cli.py`
  - Added maintenance command coverage.
- `README.md`, `AGENTS.md`, `docs/plan/roadmap.md`
  - Documented the maintenance command and behavior.

## Program Logs

The rebuild command reports observable maintenance stages:

- `[library] scanning: ...`
- `[index] rebuilt creator: ...`
- `[index] rebuilt series: ...`
- `[index] skipped manifest (...): ...`
- `[index] removed stale: ...`
- `[index] dry-run: ...`

Bad or incomplete manifests are skipped without blocking the rest of the
rebuild.

## Verification

Initial targeted check:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_library.py tests\test_cli.py -q
```

Result:

```text
82 passed
```

Final verification:

```powershell
.\clipvault.ps1 --help
.\clipvault.ps1 library rebuild-index --help
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
git diff --check
```

Result:

```text
163 passed
No broken requirements found.
compileall clean
git diff --check clean
```

## Follow-ups

- Phase 5 creator tracking can build on these indexes, because the library now
  has a recovery path when indexes become stale or inconsistent.
