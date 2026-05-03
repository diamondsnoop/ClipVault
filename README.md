# ClipVault

ClipVault is a local-first video transcript vault. It accepts a video URL, tries to fetch existing platform subtitles first, falls back to local ASR when subtitles are unavailable, and stores `srt`, `txt`, and `md` outputs in a stable platform-aware folder structure.

The current project focuses on reliable transcript acquisition and local library maintenance. Bilibili is the primary path; YouTube has been validated through the same `yt-dlp` subtitle pipeline. Broader platform support and richer library management will come later.

## Current Behavior

- Input a video URL.
- Prefer platform subtitles or automatic captions when available.
- Fall back to `faster-whisper` ASR when no subtitle is available.
- Use CUDA automatically when available, with CPU fallback.
- Store outputs under `library/<platform>/<creator>/<video title - id>/`.
- Reuse completed cached items based on `manifest.json` and actual output files.

## Quick Start

Create a local virtual environment and install the project:

```powershell
cd "E:\myproject\ClipVault"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
```

For a pinned environment, install the lock file first:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

Install `ffmpeg` separately and make sure it is available on `PATH`:

```powershell
ffmpeg -version
```

Run ClipVault:

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..."
```

Or call the module directly:

```powershell
.\.venv\Scripts\python.exe -m clipvault "https://www.bilibili.com/video/BV..."
```

## Windows NVIDIA GPU

ClipVault defaults to `--device auto`, which prefers CUDA when CTranslate2 can use it. For Windows NVIDIA GPU support without installing the full CUDA Toolkit, install the optional runtime wheels:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu-win.lock
```

The GPU lock is intentionally separate because NVIDIA runtime wheels are large. Skip this step if CPU ASR is acceptable.

You can force CPU or CUDA:

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device cpu
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device cuda
```

## Output Layout

```text
library/
  bilibili/
    Creator Name/
      _index.json               # auto-maintained creator index
      Video Title - BVxxxx/
        manifest.json
        transcript.srt
        transcript.txt
        transcript.md
        source_audio.m4a        # kept only when --keep-audio is used
      Series Name/
        _index.json             # auto-maintained series index
        Video Title - BVxxxx/
          ...
```

With `--series`, the path becomes `library/<platform>/<creator>/<series>/<video title - id>/`.

After every successful pipeline run, ClipVault automatically maintains two JSON index files:

- **Creator index** (`library/<platform>/<creator>/_index.json`) — lists all processed videos and known series for that creator.
- **Series index** (`library/<platform>/<creator>/<series>/_index.json`) — created only when `--series` is used, lists videos in that series.

Indexes are plain JSON files — no database, no external dependencies. They are updated on both new processing runs and cache hits, so even pre-index caches get indexed on access.

Old `library/<creator>/<video title - id>/` folders remain readable for cache compatibility when their manifest and output files are complete.

## Common Commands

```powershell
# Re-fetch even if a completed manifest and transcript files already exist
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --force

# Use a custom library root
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --library "E:\VideoSubs"

# Assign a video to a series (groups videos under a series folder)
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --series "睡前消息"

# Use a smaller ASR model
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --model tiny
```

## Auto Series Rules

Without ``--series``, ClipVault can assign videos to a series automatically
using local title-matching rules.

Rules are stored per creator in:

```text
library/<platform>/<creator>/_series_rules.json
```

Format:

```json
{
  "schema_version": 1,
  "rules": [
    {
      "series": "睡前消息",
      "title_contains": ["睡前消息"],
      "title_regex": null
    },
    {
      "series": "History of the Middle East",
      "title_contains": ["History of the Middle East"],
      "title_regex": null
    }
  ]
}
```

- **``title_contains``**: any of these strings appears in the video title (case-sensitive).
- **``title_regex``**: optional regex pattern matched via ``re.search``.
- First matching rule wins (rules are evaluated in file order).
- File must be created manually — no CLI management commands yet.
- Manually passed ``--series`` always takes priority over auto-rules.
- This is local title-based matching, not AI recognition and not creator
  subscription.

## Repository Hygiene

Do not commit generated data or local runtime folders:

- `.venv/`
- `library/`
- model caches
- runtime logs
- generated subtitle files
