# 2026-05-04: Phase 3 Step 3 — YouTube Transcript Path Validation

## Target

Validate YouTube subtitle acquisition in the real-world pipeline:
- Manual/auto subtitle selection with correct language priority
- ASR fallback when no subtitles exist
- Output directory structure, manifest fields, and subtitle_source correctness
- Cache-hit behavior for re-processed videos

## Samples

All tests used `--force` to bypass cache and exercise the full pipeline.

| Scenario | URL | Title | Duration | Channel |
|---|---|---|---|---|
| A — Platform captions | https://www.youtube.com/watch?v=Vdd6EOlRVbg | When did Islamic Extremism become a Threat? \| History of the Middle East 1600-1800 - 3/21 | 38:17 | Jabzy |
| B — ASR fallback | https://www.youtube.com/watch?v=2ZrWHtvSog4 | 1-Minute Audio Test for Stereo Speakers & Headphones | 1:00 | Outlier Audio |

## Steps

1. Checked subtitle availability via `yt-dlp --list-subs` for candidate videos.
2. Ran `python -m clipvault <URL> --force --verbose` for Scenario A.
3. Ran `python -m clipvault <URL> --force --model small --device cpu` for Scenario B (no captions → ASR).
4. Inspected manifest.json, output files, and cache-hit behavior.
5. Verified all existing unit tests still pass.

## Results

### Scenario A — YouTube Automatic Captions

```
[pipeline] processing https://www.youtube.com/watch?v=Vdd6EOlRVbg
[metadata] ok: "When did Islamic Extremism become a Threat? | History of the Middle East 1600-1800 - 3/21" by Jabzy
[platform] youtube
[subtitle] language priority: en, zh-CN, zh-Hans, zh
[subtitle] found 983 segments from automatic_caption:en-orig:json3
[pipeline] using automatic_caption:en-orig:json3
[export] srt: ...\transcript.srt (75738 bytes)
[export] txt: ...\transcript.txt (46358 bytes)
[export] md:  ...\transcript.md (48589 bytes)
```

**Correct behavior:**
- Platform correctly identified as `youtube`.
- Language priority logged as `en, zh-CN, zh-Hans, zh` (YouTube order).
- English selected: `en-orig` matched `en` in priority list via `startswith()`.
- json3 format chosen (highest ext priority within English).
- Output path: `library/youtube/Jabzy/When did Islamic Extremism... - Vdd6EOlRVbg/`
- Manifest includes `subtitle_source: "automatic_caption:en-orig:json3"`, `asr_model: null`, `asr_device: null`.
- All three output files generated with correct content.

### Scenario B — ASR Fallback

```
[pipeline] processing https://www.youtube.com/watch?v=2ZrWHtvSog4
[metadata] ok: "1-Minute Audio Test for Stereo Speakers & Headphones" by Outlier Audio
[platform] youtube
[subtitle] language priority: en, zh-CN, zh-Hans, zh
[subtitle] no platform subtitles available
[pipeline] no subtitles found, falling back to ASR
[audio] downloading audio from ...
[asr] model=...faster-whisper-small device=cpu compute_type=int8
[export] srt: ...\transcript.srt (43 bytes)
[export] txt: ...\transcript.txt (17 bytes)
[export] md:  ...\transcript.md (242 bytes)
```

**Correct behavior:**
- No subtitles/captions detected → `[subtitle] no platform subtitles available`.
- ASR fallback triggered: `[pipeline] no subtitles found, falling back to ASR`.
- Audio downloaded successfully (791 KiB, ~2s).
- Cached `small` model loaded on CPU with int8 compute.
- Manifest includes `subtitle_source: "asr:faster-whisper"`, `asr_model: "small"`, `asr_device: "cpu"`.
- Second run without `--force` returned `status: "cached"`.

### Cache hit verification

```
$ python -m clipvault "https://www.youtube.com/watch?v=2ZrWHtvSog4"
{ "status": "cached", ... }
```

`is_completed()` correctly identified the completed manifest and existing output files.

## Problems Found

**None.** Both subtitle and ASR paths completed without errors.

Minor observations (not blocking):
- `en-orig` (YouTube's "English Original" auto-caption) is selected over plain `en` when both exist at the same priority, because both match `en` via `startswith`. This is acceptable — the content is the same English ASR track.
- The `tiny` ASR model has a dangling symlink in the HF cache (target drive not mounted). The `small` model works. This is a local environment issue, not a code bug.

## Verification

```
pytest -q                              # 85 passed
clipvault --help                        # CLI unchanged
pip check                               # no broken deps
compileall -q clipvault tests           # clean
git diff --check                        # no whitespace errors
```

## Follow-ups

- **Find a stable no-caption YouTube sample** for automated ASR regression. The audio-test video used in Scenario B is a valid sample but is not from the AGENTS.md-recommended Jabzy series.
- **Document ASR model pre-download procedure** for new users. Current error message says "pre-download the model" but doesn't give the exact `faster-whisper-download` command.
- Phase 4: Series management and creator indexes.
