from __future__ import annotations

from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from .auth import apply_ytdlp_cookies
from .adapters import PLATFORMS, adapter_for_url, identify_platform, platform_languages
from .runtime_logs import emit_log


def _display_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text or text in {"untitled", "unknown", "unknown-uploader", "unknown-id"}:
        return fallback
    return text


def _flat_entry_url(entry: dict[str, Any], *, source_url: str) -> str | None:
    adapter = adapter_for_url(source_url)
    return adapter.flat_entry_url(entry, source_url=source_url) if adapter else None


def extract_info(url: str, *, verbose: bool, cookies: Path | str | None = None) -> dict[str, Any]:
    emit_log("metadata", f"开始提取视频信息：{url}")
    opts: dict[str, Any] = {
        "quiet": not verbose,
        "no_warnings": not verbose,
        "skip_download": True,
        "noplaylist": True,
        "proxy": "",
    }
    apply_ytdlp_cookies(opts, cookies)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise RuntimeError(
            f"获取视频元数据失败：{url}。请检查链接、网络连接，"
            "并确认 yt-dlp 是否需要更新：`pip install -U yt-dlp`。"
        ) from exc
    if not isinstance(info, dict):
        raise RuntimeError(f"yt-dlp 没有返回可用的视频元数据：{url}。")
    title = _display_text(info.get("title"), "未命名视频")
    uploader = _display_text(info.get("uploader"), "未知创作者")
    emit_log("metadata", f"元数据提取成功：{title} / {uploader}", level="success")
    return info


def extract_creator_entries(
    url: str,
    *,
    limit: int,
    verbose: bool,
    cookies: Path | str | None = None,
) -> list[dict[str, Any]]:
    emit_log("creator", f"开始抓取创作者最近条目：{url}")
    opts: dict[str, Any] = {
        "quiet": not verbose,
        "no_warnings": not verbose,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": max(1, limit),
        "ignoreerrors": True,
        "proxy": "",
    }
    apply_ytdlp_cookies(opts, cookies)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise RuntimeError(
            f"抓取创作者条目失败：{url}。请检查链接、网络连接，"
            "并确认 yt-dlp 是否支持该创作者页面。"
        ) from exc
    if not isinstance(info, dict):
        raise RuntimeError(f"yt-dlp 没有返回可用的创作者元数据：{url}。")
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
    emit_log("creator", f"已发现 {len(entries)} 个候选条目", level="success")
    return entries


def download_audio(url: str, video_dir: Path, *, verbose: bool, cookies: Path | str | None = None) -> Path:
    emit_log("audio", f"开始下载音频：{url}")
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
    apply_ytdlp_cookies(opts, cookies)
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    matches = sorted(video_dir.glob("source_audio.*"))
    if not matches:
        raise RuntimeError(
            "音频下载流程已结束，但没有找到 source_audio 文件。"
            "请确认 ffmpeg 已安装并且可从 PATH 调用。"
        )
    emit_log("audio", f"音频已保存到：{matches[0]}", level="success")
    return matches[0]
