# 2026-05-04: Phase 4 Step 3 Review Fix — Malformed Rule Hardening

## Target

Harden `_series_rules.json` parsing against malformed user-written content.
The original `match_series_from_title()` assumed every item in `rules` is a
`dict`, crashing on bare numbers, strings, lists, or nulls.

## Problem

```json
{
  "rules": [
    123,
    {"series": "睡前消息", "title_contains": ["睡前消息"]}
  ]
}
```

`rule.get("series")` on the integer `123` raises `AttributeError`, taking
down the entire pipeline. The same crash occurs for any non-dict item.

## Fix

### `match_series_from_title()`

Added `isinstance(rule, dict)` guard at the top of the loop:

```python
if not isinstance(rule, dict):
    print("[series] invalid rule skipped: expected object", file=sys.stderr)
    continue
```

Non-dict items are silently skipped (with a diagnostic log line); the next
valid rule continues matching normally.

### `load_series_rules()`

Added diagnostic logging for two previously-silent failures:

- Top-level JSON not an object → `[series] invalid rules file: expected object`
- `rules` field not a list → `[series] invalid rules file: rules must be a list`

Both remain non-blocking and return `None`.

## New Tests (6 added, 152 total)

- `test_match_skips_non_dict_rule` — integer before valid rule still matches
- `test_match_skips_non_dict_rule_log` — skipped item produces log message
- `test_match_various_non_dict_items_never_crash` — None, str, int, float,
  list, bool all handled without exception
- `test_load_rules_not_a_dict_logs` — top-level array diagnostic
- `test_load_rules_not_a_list_logs` — non-list rules diagnostic
- `test_resolve_series_with_malformed_rule` — full resolve_series path
  survives a malformed rule and matches the next valid one

## Verification

```
pytest -q                              # 152 passed
clipvault --help                        # no regression
pip check                               # no broken deps
compileall -q clipvault tests           # clean
git diff --check                        # no whitespace errors
```

## Files Changed

- `clipvault/series_rules.py` — non-dict guard in `match_series_from_title`,
  diagnostic logging in `load_series_rules`
- `tests/test_series_rules.py` — 6 new hardening tests
