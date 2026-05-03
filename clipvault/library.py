from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def video_directory(library: Path, *, uploader: str, title: str, video_id: str) -> Path:
    return library / safe_name(uploader) / safe_name(f"{title} - {video_id}")


def build_manifest(
    info: dict[str, Any],
    *,
    url: str,
    title: str,
    uploader: str,
    video_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "title": title,
        "uploader": uploader,
        "video_id": video_id,
        "source_url": url,
        "webpage_url": info.get("webpage_url"),
        "platform": guess_platform(url),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "description": info.get("description"),
        "creator_id": info.get("channel_id") or info.get("uploader_id"),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "subtitle_source": None,
        "asr_model": None,
        "asr_device": None,
        "output_files": [],
    }


def update_manifest(path: Path, **updates: Any) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(updates)
    write_json(path, data)


def guess_platform(url: str) -> str:
    lower = url.lower()
    if "bilibili.com" in lower or "b23.tv" in lower:
        return "bilibili"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    if "douyin.com" in lower:
        return "douyin"
    return "unknown"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def first_text(data: dict[str, Any], *keys: str, default: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def safe_name(value: str, *, max_length: int = 120) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        cleaned = "untitled"
    return cleaned[:max_length].rstrip(" .")

