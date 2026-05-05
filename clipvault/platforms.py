from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from .adapters import PLATFORMS, adapter_for_url, identify_platform, platform_languages


def _flat_entry_url(entry: dict[str, Any], *, source_url: str) -> str | None:
    adapter = adapter_for_url(source_url)
    return adapter.flat_entry_url(entry, source_url=source_url) if adapter else None


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


def extract_creator_entries(url: str, *, limit: int, verbose: bool) -> list[dict[str, Any]]:
    print(f"[creator] fetching recent entries from {url}", file=sys.stderr)
    opts: dict[str, Any] = {
        "quiet": not verbose,
        "no_warnings": not verbose,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": max(1, limit),
        "ignoreerrors": True,
        "proxy": "",
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch creator entries from {url}. Check the URL, network connection, "
            f"and whether yt-dlp supports this creator page."
        ) from exc
    if not isinstance(info, dict):
        raise RuntimeError(f"yt-dlp did not return creator metadata for {url}.")
    raw_entries = info.get("entries") or []
    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        video_url = _flat_entry_url(entry, source_url=url)
        if not video_url:
            continue
        entries.append({
            "id": entry.get("id"),
            "title": entry.get("title") or "untitled",
            "url": video_url,
            "duration": entry.get("duration"),
            "upload_date": entry.get("upload_date"),
        })
        if len(entries) >= limit:
            break
    print(f"[creator] discovered: {len(entries)}", file=sys.stderr)
    return entries


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
