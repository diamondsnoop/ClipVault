from __future__ import annotations

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
        "",
        "## 字幕正文",
        "",
    ]
    lines.extend(f"- `{format_clock(seg.start)}` {seg.text}" for seg in segments)
    lines.append("")
    return "\n".join(lines)


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

