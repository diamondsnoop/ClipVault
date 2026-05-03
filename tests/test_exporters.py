from __future__ import annotations

from clipvault.exporters import (
    format_clock,
    format_srt_time,
    to_markdown,
    to_plain_text,
    to_srt,
)
from clipvault.models import SubtitleSegment


def _segments() -> list[SubtitleSegment]:
    return [
        SubtitleSegment(start=1.0, end=3.5, text="大家好 欢迎收看本期视频"),
        SubtitleSegment(start=4.0, end=6.0, text="今天我们来聊一个有趣的话题"),
        SubtitleSegment(start=10.5, end=15.25, text="第三段内容"),
    ]


# --- format_srt_time ---


def test_format_srt_time():
    assert format_srt_time(0.0) == "00:00:00,000"
    assert format_srt_time(1.0) == "00:00:01,000"
    assert format_srt_time(65.5) == "00:01:05,500"
    assert format_srt_time(3661.123) == "01:01:01,123"


# --- format_clock ---


def test_format_clock_without_hours():
    assert format_clock(0) == "00:00"
    assert format_clock(65) == "01:05"
    assert format_clock(3599) == "59:59"


def test_format_clock_with_hours():
    assert format_clock(3600) == "01:00:00"
    assert format_clock(3661) == "01:01:01"


# --- to_srt ---


def test_to_srt():
    result = to_srt(_segments())
    assert result.startswith("1\n00:00:01,000 --> 00:00:03,500\n大家好 欢迎收看本期视频")
    assert "2\n00:00:04,000 --> 00:00:06,000\n今天我们来聊一个有趣的话题" in result
    assert "3\n00:00:10,500 --> 00:00:15,250\n第三段内容" in result
    assert result.endswith("\n")


def test_to_srt_ordering():
    result = to_srt(_segments())
    assert result.count("\n\n") >= 2  # blank line separator between entries
    assert result.startswith("1\n")


def test_to_srt_empty():
    assert to_srt([]) == "\n"


# --- to_plain_text ---


def test_to_plain_text():
    result = to_plain_text(_segments())
    assert "[00:01] 大家好 欢迎收看本期视频" in result
    assert "[00:04] 今天我们来聊一个有趣的话题" in result
    assert "[00:10] 第三段内容" in result
    assert result.endswith("\n")


def test_to_plain_text_empty():
    assert to_plain_text([]) == "\n"


# --- to_markdown ---


def test_to_markdown():
    result = to_markdown(
        title="Test Video",
        uploader="TestCreator",
        url="https://example.com/video",
        video_id="VID001",
        source="subtitle:en:json3",
        segments=_segments(),
    )
    assert "# Test Video" in result
    assert "来源：https://example.com/video" in result
    assert "UP主：TestCreator" in result
    assert "视频ID：VID001" in result
    assert "字幕来源：subtitle:en:json3" in result
    assert "## 字幕正文" in result
    assert "`00:01` 大家好 欢迎收看本期视频" in result
    assert result.endswith("\n")


def test_to_markdown_empty_segments():
    result = to_markdown(
        title="Empty",
        uploader="U",
        url="https://example.com",
        video_id="X",
        source="none",
        segments=[],
    )
    assert "# Empty" in result
    assert "## 字幕正文" in result
    assert result.count("- `") == 0
