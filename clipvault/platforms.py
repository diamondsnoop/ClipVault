from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

# ── Platform registry ──────────────────────────────────────────────────
# Single source of truth for platform identification and capabilities.
# Add a new entry here when supporting a new video platform.

PLATFORMS: dict[str, dict[str, Any]] = {
    "bilibili": {
        "domains": ("bilibili.com", "b23.tv"),
        "languages": ("zh-CN", "zh-Hans", "zh-Hans-CN", "zh", "cmn-Hans-CN", "en"),
    },
    "youtube": {
        "domains": ("youtube.com", "youtu.be"),
        "languages": ("en", "zh-CN", "zh-Hans", "zh"),
    },
    "douyin": {
        "domains": ("douyin.com",),
        "languages": ("zh-CN", "zh-Hans", "zh"),
    },
}


def _domain_match(hostname: str, domain: str) -> bool:
    """Return True when *hostname* exactly equals *domain* or is a
    subdomain of *domain* (e.g. ``www.youtube.com`` matches ``youtube.com``)."""
    hostname = hostname.lower()
    domain = domain.lower()
    return hostname == domain or hostname.endswith("." + domain)


def identify_platform(url: str) -> str:
    """Identify the video platform from a URL.

    Parses the URL and matches the hostname against the registered
    *domains* in :data:`PLATFORMS`.  Subdomain matches (e.g.
    ``www.youtube.com`` → ``youtube.com``) are accepted; unrelated
    domains that happen to contain a pattern string (e.g.
    ``notyoutube.com``, ``youtube.com.evil.test``) are rejected.

    Returns a platform key registered in PLATFORMS, or ``"unknown"``.
    """
    try:
        hostname = urllib.parse.urlparse(url).hostname
    except Exception:
        hostname = None
    if not hostname:
        return "unknown"

    for name, config in PLATFORMS.items():
        for domain in config["domains"]:
            if _domain_match(hostname, domain):
                return name
    return "unknown"


def platform_languages(platform: str) -> tuple[str, ...]:
    """Preferred subtitle language tags for *platform*, in priority order."""
    info = PLATFORMS.get(platform)
    return info["languages"] if info else ("en",)


def _flat_entry_url(entry: dict[str, Any]) -> str | None:
    video_url = entry.get("webpage_url") or entry.get("url")
    if isinstance(video_url, str) and urllib.parse.urlparse(video_url).scheme:
        return video_url
    video_id = entry.get("id")
    if entry.get("ie_key") == "Youtube" and video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return video_url if isinstance(video_url, str) and video_url.strip() else None


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
        video_url = _flat_entry_url(entry)
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
