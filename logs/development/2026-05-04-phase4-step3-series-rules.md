# 2026-05-04: Phase 4 Step 3 — Title-based Auto Series Rules

## Target

Add optional title-matching rules so ClipVault can auto-assign a series when
`--series` is not explicitly provided. Rules are per-creator JSON files,
matched locally — no AI, no network access, no creator subscriptions.

## Design

### Rule file

`library/<platform>/<creator>/_series_rules.json`

```json
{
  "schema_version": 1,
  "rules": [
    {
      "series": "睡前消息",
      "title_contains": ["睡前消息"],
      "title_regex": null
    }
  ]
}
```

- `title_contains`: any keyword in the list appears in the video title
  (case-sensitive `in` check).
- `title_regex`: optional `re.search` pattern.
- First matching rule wins (file order).
- A rule with empty/normalized-to-None series is skipped.
- A rule with no `title_contains` and no `title_regex` is skipped.
- A bad regex is logged and that rule is skipped (non-blocking).
- Missing/broken rule file is non-blocking (logged).

### Integration

- `resolve_series()` in `series_rules.py` is called after metadata extraction
  in `process_video()`.
- If `explicit_series` (from `--series`) is non-None after normalization, it
  is returned immediately with source `"manual"`.
- Otherwise the rules file is loaded and matched; a match returns
  `(series, "rule")`.
- Result dicts now include `series` and `series_source` fields.

## Changes

- `clipvault/series_rules.py` — new module (4 functions).
- `clipvault/cli.py` — import `resolve_series`, defer series resolution until
  after metadata, add `series`/`series_source` to result.
- `tests/test_series_rules.py` — 21 new tests.
- `tests/test_cli.py` — 5 new tests (auto, manual override, no-rules, cache).
- `README.md` — auto series rules section.
- `AGENTS.md` — auto series rules, module listing, roadmap updated.
- `docs/plan/roadmap.md` — Phase 4 Step 3 marked done.

## Verification

```
pytest -q                              # 146 passed
clipvault --help                        # no regression
pip check                               # no broken deps
compileall -q clipvault tests           # clean
git diff --check                        # no whitespace errors
```

## Smoke Test

Created `library/youtube/jawed/_series_rules.json`:

```json
{
  "schema_version": 1,
  "rules": [
    {
      "series": "YouTube History",
      "title_contains": ["Me at the zoo"],
      "title_regex": null
    }
  ]
}
```

Ran:

```
.\clipvault.ps1 "https://www.youtube.com/watch?v=jNQXAC9IVRw" --force
```

Verified:
- Output path: `library/youtube/jawed/YouTube History/Me at the zoo - jNQXAC9IVRw/`
- Manifest `series` = `"YouTube History"`
- Creator index and series index updated
- Log shows `[series] auto: YouTube History`

Manual override:

```
.\clipvault.ps1 "https://www.youtube.com/watch?v=jNQXAC9IVRw" --series "Manual Override" --force
```

Verified:
- Uses `Manual Override` path, not the auto-rule.
- Log does not show `[series] auto:`.
- Manifest `series` = `"Manual Override"`.

## Follow-ups

- **Rule management CLI** — commands to add/list/remove rules. Not done here.
- **Historical migration** — retroactively apply rules to already-processed
  videos. Not done here.
- **Creator subscription** — follow creators and batch-fetch new videos.
  Requires the index foundation. Not done here.
