# ClipVault

ClipVault is a local-first video transcript vault. It accepts a video URL, tries to fetch existing platform subtitles first, falls back to local ASR when subtitles are unavailable, and stores `srt`, `txt`, and `md` outputs in a stable folder structure.

The current prototype focuses on Bilibili links. Broader platform support and richer library management will come later.

## Current Behavior

- Input a Bilibili video URL.
- Prefer platform subtitles or automatic captions when available.
- Fall back to `faster-whisper` ASR when no subtitle is available.
- Use CUDA automatically when available, with CPU fallback.
- Store outputs under `library/<creator>/<video title - id>/`.

## Quick Start

Create a local virtual environment and install the project:

```powershell
cd "C:\Users\24967\Documents\New project"
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
  Creator Name/
    Video Title - BVxxxx/
      manifest.json
      transcript.srt
      transcript.txt
      transcript.md
      source_audio.m4a        # kept only when --keep-audio is used
```

## Common Commands

```powershell
# Re-fetch even if transcript.md already exists
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --force

# Use a custom library root
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --library "E:\VideoSubs"

# Use a smaller ASR model
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --model tiny
```

## Repository Hygiene

Do not commit generated data or local runtime folders:

- `.venv/`
- `library/`
- model caches
- logs
- generated subtitle files
