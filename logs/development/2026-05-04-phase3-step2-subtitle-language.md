# 2026-05-04: Phase 3 Step 2 — Subtitle Language Selection

## Target

Make subtitle selection respect per-platform language preferences so that
Bilibili picks Chinese subtitles first, YouTube picks English first, and
ext format priority still works within the chosen language.

## Steps

1. **`subtitles.py` — platform-aware language priority**
   - `get_platform_subtitles(info, *, platform: str)` now accepts a `platform`
     parameter instead of using the hardcoded `LANG_PRIORITY`.
   - Calls `platform_languages(platform)` to get the per-platform priority list.
   - `language_priority()` accepts an optional `priorities` parameter (default
     `LANG_PRIORITY` for backward compatibility).
   - Chinese fallback slot uses `len(priorities) + 10` instead of hardcoded `10`.
   - Added `[subtitle] language priority: ...` diagnostic log.

2. **`cli.py` — pass platform to subtitle selection**
   - `process_video()` calls `get_platform_subtitles(info, platform=platform)`.

3. **Tests**
   - `test_language_priority_bilibili` — zh-CN at index 0, en at 5
   - `test_language_priority_youtube` — en at index 0, zh-CN at 1
   - `test_language_priority_unknown_platform` — only ("en",), zh fallback at 11
   - `test_get_platform_subtitles_priority` — Bilibili picks zh-Hans over en
   - `test_get_platform_subtitles_youtube_prefers_en` — YouTube picks en over zh-Hans
   - `test_get_platform_subtitles_ext_priority` — json3 preferred over vtt within same lang
   - `test_get_platform_subtitles_no_subtitles` — empty returns ("none", [])
   - All 85 tests pass.

## Verification

```
pytest -q                              # 85 passed
python -m clipvault --help             # CLI unchanged
pip check                              # no broken deps
compileall -q clipvault tests          # clean
git diff --check                       # no whitespace errors
```

## Follow-ups

- Phase 3 step 3: validate YouTube manual subtitles and audio fallback with
  real links.
- No Douyin work until extraction reliability is proven.
