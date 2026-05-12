from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from .auth import build_authenticated_opener
from .models import SubtitleSegment
from .platforms import platform_languages
from .runtime_logs import emit_log
from .text import clean_text, strip_tags

# Default language priority used when no platform context is available.
# Platform-specific overrides live in platforms.PLATFORMS[]["languages"].
LANG_PRIORITY = (
    "zh-CN",
    "zh-Hans",
    "zh-Hans-CN",
    "zh",
    "cmn-Hans-CN",
    "en",
)


def get_platform_subtitles(
    info: dict[str, Any],
    *,
    platform: str,
    cookies: Path | str | None = None,
) -> tuple[list[SubtitleSegment], str]:
    priorities = platform_languages(platform)
    emit_log("subtitle", f"字幕语言优先级：{', '.join(priorities)}")

    tracks = []
    for source_name, field in (("subtitle", "subtitles"), ("automatic_caption", "automatic_captions")):
        subtitle_map = info.get(field) or {}
        if not isinstance(subtitle_map, dict):
            continue
        for lang, entries in subtitle_map.items():
            priority = language_priority(lang, priorities)
            if priority is None:
                continue
            for entry in entries or []:
                if isinstance(entry, dict) and entry.get("url"):
                    tracks.append((priority, source_name, lang, entry))

    tracks.sort(key=lambda item: (item[0], preferred_ext_rank(item[3].get("ext"))))
    for _, source_name, lang, entry in tracks:
        try:
            raw = fetch_text(entry["url"], cookies=cookies)
            segments = parse_subtitle(raw, entry.get("ext") or "")
            if segments:
                source_desc = f"{source_name}:{lang}:{entry.get('ext') or 'unknown'}"
                emit_log("subtitle", f"已从 {source_desc} 获取 {len(segments)} 个片段", level="success")
                return segments, source_desc
        except Exception:
            continue
    emit_log("subtitle", "当前平台没有可用字幕", level="warning")
    return [], "none"


def language_priority(lang: str, priorities: tuple[str, ...] = LANG_PRIORITY) -> int | None:
    normalized = lang.strip()
    for index, candidate in enumerate(priorities):
        if normalized == candidate or normalized.lower().startswith(candidate.lower()):
            return index
    # Chinese variants not listed still get a slot (after all explicit entries).
    if normalized.lower().startswith("zh"):
        return len(priorities) + 10
    return None


def preferred_ext_rank(ext: str | None) -> int:
    return {"json": 0, "json3": 1, "vtt": 2, "srt": 3}.get((ext or "").lower(), 9)


def fetch_text(url: str, *, cookies: Path | str | None = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    opener = build_authenticated_opener(cookies)
    with opener.open(req, timeout=30) as response:  # noqa: S310 - user supplied subtitle URL
        return response.read().decode("utf-8", errors="replace")


def parse_subtitle(raw: str, ext: str) -> list[SubtitleSegment]:
    text = raw.lstrip("\ufeff").strip()
    if not text:
        return []
    if ext.lower() in {"json", "json3"} or text.startswith("{"):
        return parse_json_subtitle(text)
    if "WEBVTT" in text[:64]:
        return parse_vtt(text)
    return parse_srt(text)


def parse_json_subtitle(raw: str) -> list[SubtitleSegment]:
    data = json.loads(raw)
    body = data.get("body") or data.get("events") or []
    segments: list[SubtitleSegment] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        if "content" in item:
            start = float(item.get("from", 0))
            end = float(item.get("to", start))
            text = clean_text(str(item.get("content", "")))
        else:
            start = float(item.get("tStartMs", 0)) / 1000
            duration = float(item.get("dDurationMs", 0)) / 1000
            end = start + duration
            segs = item.get("segs") or []
            text = clean_text("".join(str(seg.get("utf8", "")) for seg in segs if isinstance(seg, dict)))
        if text:
            segments.append(SubtitleSegment(start=start, end=max(end, start), text=text))
    return segments


def parse_vtt(raw: str) -> list[SubtitleSegment]:
    segments: list[SubtitleSegment] = []
    lines = [line.strip("\ufeff") for line in raw.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue
        start_s, end_s = split_time_range(line)
        i += 1
        content: list[str] = []
        while i < len(lines) and lines[i].strip():
            content.append(strip_tags(lines[i].strip()))
            i += 1
        text = clean_text(" ".join(content))
        if text:
            segments.append(SubtitleSegment(parse_time(start_s), parse_time(end_s), text))
    return segments


def parse_srt(raw: str) -> list[SubtitleSegment]:
    segments: list[SubtitleSegment] = []
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n"))
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        time_line = next((line for line in lines if "-->" in line), "")
        if not time_line:
            continue
        idx = lines.index(time_line)
        start_s, end_s = split_time_range(time_line)
        text = clean_text(" ".join(strip_tags(line) for line in lines[idx + 1 :]))
        if text:
            segments.append(SubtitleSegment(parse_time(start_s), parse_time(end_s), text))
    return segments


def split_time_range(line: str) -> tuple[str, str]:
    left, right = line.split("-->", 1)
    return left.strip(), right.strip().split()[0]


def parse_time(value: str) -> float:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = "0", parts[0], parts[1]
    else:
        return float(value)
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
