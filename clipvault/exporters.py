from __future__ import annotations

import re
from pathlib import Path

from .models import SubtitleSegment


def write_outputs(
    *,
    video_dir: Path,
    title: str,
    uploader: str,
    url: str,
    video_id: str,
    source: str,
    segments: list[SubtitleSegment],
) -> None:
    (video_dir / "transcript.srt").write_text(to_srt(segments), encoding="utf-8")
    (video_dir / "transcript.txt").write_text(to_plain_text(segments), encoding="utf-8")
    (video_dir / "transcript.md").write_text(
        to_markdown(title=title, uploader=uploader, url=url, video_id=video_id, source=source, segments=segments),
        encoding="utf-8",
    )


def to_srt(segments: list[SubtitleSegment]) -> str:
    blocks = []
    for index, seg in enumerate(segments, start=1):
        blocks.append(f"{index}\n{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}\n{seg.text}")
    return "\n\n".join(blocks) + "\n"


def to_plain_text(segments: list[SubtitleSegment]) -> str:
    return "\n".join(f"[{format_clock(seg.start)}] {seg.text}" for seg in segments) + "\n"


def to_markdown(
    *,
    title: str,
    uploader: str,
    url: str,
    video_id: str,
    source: str,
    segments: list[SubtitleSegment],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 来源：{url}",
        f"- UP主：{uploader}",
        f"- 视频ID：{video_id}",
        f"- 字幕来源：{source}",
        f"- 片段数：{len(segments)}",
        "",
        "## 字幕正文",
        "",
    ]
    paragraphs = to_markdown_paragraphs(segments)
    if paragraphs:
        for paragraph in paragraphs:
            lines.append(paragraph)
            lines.append("")
    else:
        lines.append("（无字幕正文）")
        lines.append("")
    return "\n".join(lines)


def to_markdown_paragraphs(
    segments: list[SubtitleSegment],
    *,
    paragraph_gap_seconds: float = 4.0,
    sentence_gap_seconds: float = 3.0,
    max_paragraph_chars: int = 180,
) -> list[str]:
    paragraphs: list[str] = []
    current_parts: list[str] = []
    current_chars = 0
    previous_end: float | None = None

    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue

        gap = None if previous_end is None else max(0.0, segment.start - previous_end)
        if current_parts and _should_start_new_paragraph(
            current_text=current_parts[-1],
            current_chars=current_chars,
            gap_seconds=gap,
            paragraph_gap_seconds=paragraph_gap_seconds,
            sentence_gap_seconds=sentence_gap_seconds,
            max_paragraph_chars=max_paragraph_chars,
        ):
            paragraphs.append(_merge_paragraph_parts(current_parts))
            current_parts = []
            current_chars = 0

        current_parts.append(text)
        current_chars += len(text)
        previous_end = segment.end

    if current_parts:
        paragraphs.append(_merge_paragraph_parts(current_parts))

    return paragraphs


def _should_start_new_paragraph(
    *,
    current_text: str,
    current_chars: int,
    gap_seconds: float | None,
    paragraph_gap_seconds: float,
    sentence_gap_seconds: float,
    max_paragraph_chars: int,
) -> bool:
    if gap_seconds is None:
        return False
    if gap_seconds >= paragraph_gap_seconds:
        return True
    if current_chars >= max_paragraph_chars:
        return True
    return gap_seconds >= sentence_gap_seconds and _ends_sentence(current_text)


def _merge_paragraph_parts(parts: list[str]) -> str:
    merged = " ".join(part.strip() for part in parts if part.strip())
    merged = re.sub(r"\s+([，。！？；：、,.!?;:])", r"\1", merged)
    merged = re.sub(r"([（《“])\s+", r"\1", merged)
    merged = re.sub(r"\s+([）》”])", r"\1", merged)
    return merged.strip()


def _ends_sentence(text: str) -> bool:
    return text.rstrip().endswith(("。", "！", "？", ".", "!", "?"))


def format_srt_time(seconds: float) -> str:
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def format_clock(seconds: float) -> str:
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"

