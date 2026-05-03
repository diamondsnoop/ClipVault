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
| C — Manual subtitles | https://www.youtube.com/watch?v=jNQXAC9IVRw | Me at the zoo | 0:19 | jawed |

## Steps

1. Checked subtitle availability via `yt-dlp --list-subs` for candidate videos.
2. Ran `python -m clipvault <URL> --force --verbose` for Scenario A.
3. Ran `python -m clipvault <URL> --force --model small --device cpu` for Scenario B (no captions → ASR).
4. Searched Jabzy videos for manual subtitles — none found. Selected "Me at the zoo" (jNQXAC9IVRw), the first YouTube video ever uploaded, which has manually uploaded English and German subtitles.
5. Ran `python -m clipvault <URL> --force --verbose` for Scenario C.
6. Inspected manifest.json, output files, and cache-hit behavior.
7. Verified all existing unit tests still pass.

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

### Scenario C — YouTube Manual Subtitles

```
[pipeline] processing https://www.youtube.com/watch?v=jNQXAC9IVRw
[metadata] ok: "Me at the zoo" by jawed
[platform] youtube
[subtitle] language priority: en, zh-CN, zh-Hans, zh
[subtitle] found 6 segments from subtitle:en:json3
[pipeline] using subtitle:en:json3
[export] srt: ...\transcript.srt
[export] txt: ...\transcript.txt
[export] md:  ...\transcript.md
```

**Correct behavior:**
- Manual subtitle detected as `subtitle:en:json3` (NOT `automatic_caption:...`).
- English selected per YouTube language priority (`en` at index 0).
- json3 format chosen (highest ext priority within English).
- Output path: `library/youtube/jawed/Me at the zoo - jNQXAC9IVRw/`.
- Manifest includes `subtitle_source: "subtitle:en:json3"`, `asr_model: null`, `asr_device: null`.
- All three output files generated.

**Note:** No Jabzy video in the History of the Middle East series has manual subtitles. "Me at the zoo" was chosen as a minimal, stable, widely-known example with confirmed manually uploaded subtitles (en and de). The manual-subtitle pipeline code path is identical regardless of channel — the selection logic only depends on the `subtitles` dict in yt-dlp's output, which this video provides.

```
$ python -m clipvault "https://www.youtube.com/watch?v=2ZrWHtvSog4"
{ "status": "cached", ... }
```

`is_completed()` correctly identified the completed manifest and existing output files.

## Problems Found

**None.** All three paths (manual subtitle, automatic caption, ASR fallback) completed without errors.

Limitations noted:
- **No Jabzy manual subtitles found.** Manual subtitle validation used a non-Jabzy video ("Me at the zoo") because no video in the History of the Middle East series has manually uploaded subtitles. The code path is channel-independent.
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
