from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL


def extract_info(url: str, *, verbose: bool) -> dict[str, Any]:
    print(f"[metadata] extracting info for {url}", file=sys.stderr)
    opts: dict[str, Any] = {
        "quiet": not verbose,
        "no_warnings": not verbose,
        "skip_download": True,
        "noplaylist": True,
        "proxy": "",
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch video metadata from {url}. Check the URL and your network connection. "
            f"If the URL is correct, yt-dlp may need an update: pip install -U yt-dlp"
        ) from exc
    if not isinstance(info, dict):
        raise RuntimeError(f"yt-dlp did not return video metadata for {url}.")
    title = info.get("title", "untitled")
    uploader = info.get("uploader", "unknown")
    print(f"[metadata] ok: \"{title}\" by {uploader}", file=sys.stderr)
    return info


def download_audio(url: str, video_dir: Path, *, verbose: bool) -> Path:
    print(f"[audio] downloading audio from {url}", file=sys.stderr)
    output = str(video_dir / "source_audio.%(ext)s")
    opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": output,
        "quiet": not verbose,
        "no_warnings": not verbose,
        "noplaylist": True,
        "proxy": "",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }
        ],
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    matches = sorted(video_dir.glob("source_audio.*"))
    if not matches:
        raise RuntimeError(
            "Audio download finished, but no source_audio file was found. "
            "Check that ffmpeg is installed and available on PATH."
        )
    print(f"[audio] saved to {matches[0]}", file=sys.stderr)
    return matches[0]

