# 2026-05-04: Phase 3 Step 1 — Platform Adaptation Boundary

## Target

Define a lightweight, extensible platform-registry boundary so that future
platforms can be added by editing data structures rather than control flow.
Avoid putting more platform logic into `cli.py`.

## Steps

1. **Platform registry in `platforms.py`**
   - Added `PLATFORMS` dict with `url_patterns` and `languages` per platform.
   - Added `identify_platform(url)` — the single entry point for URL-based
     platform detection.
   - Added `platform_languages(platform)` — per-platform language preferences
     for future subtitle prioritization.

2. **`library.guess_platform()` becomes a thin delegator**
   - No longer hard-codes URL patterns; delegates to
     `platforms.identify_platform()`.
   - Remains exported from `library` so `build_manifest` and existing callers
     keep a single import path.

3. **Program log for platform detection**
   - `cli.py` prints `[platform] <name>` after identifying the platform.

4. **Tests**
   - `tests/test_platforms.py` (12 tests): covers every registered platform,
     unknown fallback, case insensitivity, edge inputs, languages per platform,
     and registry shape validation.
   - All 76 tests pass.

## Changes

- `clipvault/platforms.py` — PLATFORMS dict, identify_platform(),
  platform_languages()
- `clipvault/library.py` — guess_platform() now delegates to
  platforms.identify_platform()
- `clipvault/cli.py` — [platform] log after detection
- `tests/test_platforms.py` — new test file (12 tests)

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q        # 76 passed
.\clipvault.ps1 --help                          # CLI unchanged
.\.venv\Scripts\python.exe -m pip check         # no broken deps
.\.venv\Scripts\python.exe -m compileall -q clipvault tests  # clean
```

## Review Fix: Domain Matching Hardening

**Problem:** The initial `identify_platform()` used Python's ``in`` operator
for substring matching, which falsely identified fake domains like
``notyoutube.com`` or ``youtube.com.evil.test`` as known platforms.

**Fix:**

1. Replaced `url_patterns` with `domains` in the platform registry.
2. Added ``_domain_match(hostname, domain)`` — exact match or subdomain
   match (``hostname == domain`` or ``hostname.endswith("." + domain)``).
3. ``identify_platform()`` now parses the URL with
   ``urllib.parse.urlparse`` and extracts the hostname before matching.
4. Empty strings, non-URL strings, and unparseable inputs return
   ``"unknown"``.

**Tests added:**

- ``test_identify_fake_domains_not_matched`` (4 cases in test_platforms.py)
- ``test_guess_platform_rejects_fake_domains`` (2 cases in test_library.py)
- Registry shape test updated from `url_patterns` → `domains`
- Added edge cases: ``http://`` and whitespace input

**Verification:**

```powershell
.\.venv\Scripts\python.exe -m pytest -q        # 79 passed
.\clipvault.ps1 --help                          # CLI unchanged
.\.venv\Scripts\python.exe -m pip check         # no broken deps
.\.venv\Scripts\python.exe -m compileall -q clipvault tests  # clean
git diff --check                                # no whitespace errors
```

## Follow-ups

- Phase 3 step 2: add per-platform subtitle language selection in
  `subtitles.py` using `platform_languages()`.
- Phase 3 step 3: validate YouTube manual subtitles and audio fallback
  with real links (log under `logs/development/`).
- No Douyin work until extraction reliability is proven.
