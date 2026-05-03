from __future__ import annotations

import json

from clipvault.subtitles import (
    get_platform_subtitles,
    language_priority,
    parse_json_subtitle,
    parse_srt,
    parse_subtitle,
    parse_vtt,
    preferred_ext_rank,
    split_time_range,
)


def test_language_priority_chinese_variants():
    assert language_priority("zh-CN") == 0
    assert language_priority("zh-Hans") == 1
    assert language_priority("zh") == 3
    assert language_priority("en") == 5


def test_language_priority_unknown_returns_none():
    assert language_priority("ja") is None
    assert language_priority("ko") is None
    assert language_priority("fr") is None


def test_language_priority_zh_fallback():
    # "zh-TW" starts with "zh", matches index 3, not the fallback at 10
    assert language_priority("zh-TW") == 3
    assert language_priority("zh-HK") == 3


def test_preferred_ext_rank():
    assert preferred_ext_rank("json") == 0
    assert preferred_ext_rank("json3") == 1
    assert preferred_ext_rank("vtt") == 2
    assert preferred_ext_rank("srt") == 3
    assert preferred_ext_rank("unknown") == 9
    assert preferred_ext_rank(None) == 9


def test_split_time_range():
    left, right = split_time_range("00:01:23.456 --> 00:04:56.789")
    assert left == "00:01:23.456"
    assert right == "00:04:56.789"


def test_split_time_range_with_extra():
    left, right = split_time_range("00:00:01.000 --> 00:00:02.000 align:start")
    assert left == "00:00:01.000"
    assert right == "00:00:02.000"


# --- JSON subtitle (Bilibili format) ---


def test_parse_json_bilibili():
    raw = json.dumps(
        {
            "body": [
                {"from": 1.0, "to": 3.5, "content": "大家好 欢迎收看本期视频"},
                {"from": 4.0, "to": 6.0, "content": "今天我们来聊一个有趣的话题"},
            ]
        }
    )
    segments = parse_json_subtitle(raw)
    assert len(segments) == 2
    assert segments[0].start == 1.0
    assert segments[0].end == 3.5
    assert "大家好" in segments[0].text
    assert segments[1].start == 4.0


def test_parse_json_bilibili_with_tags():
    raw = json.dumps(
        {
            "body": [
                {"from": 0.0, "to": 2.0, "content": "Hello <i>world</i>"},
            ]
        }
    )
    segments = parse_json_subtitle(raw)
    assert len(segments) == 1
    assert segments[0].text == "Hello world"


def test_parse_json_empty_body():
    assert parse_json_subtitle("{}") == []
    assert parse_json_subtitle('{"body": []}') == []


# --- JSON3 subtitle (YouTube format) ---


def test_parse_json3_youtube():
    raw = json.dumps(
        {
            "events": [
                {"tStartMs": 1000, "dDurationMs": 2500, "segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
                {"tStartMs": 4000, "dDurationMs": 2000, "segs": [{"utf8": "Second line"}]},
            ]
        }
    )
    segments = parse_json_subtitle(raw)
    assert len(segments) == 2
    assert segments[0].start == 1.0
    assert segments[0].end == 3.5
    assert segments[0].text == "Hello world"
    assert segments[1].start == 4.0
    assert segments[1].end == 6.0


def test_parse_json3_empty_segs():
    raw = json.dumps({"events": [{"tStartMs": 0, "dDurationMs": 1000, "segs": []}]})
    segments = parse_json_subtitle(raw)
    assert len(segments) == 0


# --- VTT subtitle ---


def test_parse_vtt():
    raw = """WEBVTT

00:00:01.000 --> 00:00:03.500
大家好 欢迎收看本期视频

00:00:04.000 --> 00:00:06.000
今天我们来聊一个有趣的话题
"""
    segments = parse_vtt(raw)
    assert len(segments) == 2
    assert segments[0].start == 1.0
    assert segments[0].end == 3.5
    assert "大家好" in segments[0].text


def test_parse_vtt_with_tags():
    raw = """WEBVTT

00:00:00.000 --> 00:00:02.000
Hello <c>world</c>
"""
    segments = parse_vtt(raw)
    assert len(segments) == 1
    assert segments[0].text == "Hello world"


def test_parse_vtt_empty():
    assert parse_vtt("") == []
    assert parse_vtt("WEBVTT\n\n") == []


# --- SRT subtitle ---


def test_parse_srt():
    raw = """1
00:00:01,000 --> 00:00:03,500
大家好 欢迎收看本期视频

2
00:00:04,000 --> 00:00:06,000
今天我们来聊一个有趣的话题
"""
    segments = parse_srt(raw)
    assert len(segments) == 2
    assert segments[0].start == 1.0
    assert segments[0].end == 3.5
    assert "大家好" in segments[0].text


def test_parse_srt_multi_line():
    raw = """1
00:00:00.000 --> 00:00:03.000
First line
Second line
"""
    segments = parse_srt(raw)
    assert len(segments) == 1
    assert segments[0].text == "First line Second line"


def test_parse_srt_empty():
    assert parse_srt("") == []


# --- parse_subtitle dispatch ---


def test_parse_subtitle_dispatch_json():
    segments = parse_subtitle('{"body": [{"from": 0, "to": 1, "content": "test"}]}', "json")
    assert len(segments) == 1


def test_parse_subtitle_dispatch_srt():
    raw = "1\n00:00:01,000 --> 00:00:02,000\ntest\n"
    segments = parse_subtitle(raw, "srt")
    assert len(segments) == 1


def test_parse_subtitle_dispatch_vtt():
    raw = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\ntest\n"
    segments = parse_subtitle(raw, "vtt")
    assert len(segments) == 1


def test_parse_subtitle_dispatch_auto_json():
    segments = parse_subtitle('{"body": [{"from": 0, "to": 1, "content": "test"}]}', "unknown")
    assert len(segments) == 1


def test_parse_subtitle_empty_returns_empty():
    assert parse_subtitle("", "srt") == []
    assert parse_subtitle("   ", "vtt") == []


# ── language_priority with custom platform priorities ──────────────────


def test_language_priority_bilibili():
    """Bilibili priority: zh-CN (index 0), en (index 5)."""
    priorities = ("zh-CN", "zh-Hans", "zh-Hans-CN", "zh", "cmn-Hans-CN", "en")
    assert language_priority("zh-CN", priorities) == 0
    assert language_priority("en", priorities) == 5
    assert language_priority("ja", priorities) is None


def test_language_priority_youtube():
    """YouTube priority: en (index 0), zh-CN (index 1)."""
    priorities = ("en", "zh-CN", "zh-Hans", "zh")
    assert language_priority("en", priorities) == 0
    assert language_priority("zh-CN", priorities) == 1
    assert language_priority("zh-TW", priorities) == 3  # matches "zh"


def test_language_priority_unknown_platform():
    """Unknown platform falls back to ('en',) -- only English is known.
    Chinese variants still get a fallback slot via the zh- rule."""
    assert language_priority("en", ("en",)) == 0
    assert language_priority("zh-CN", ("en",)) == 11  # len(("en",)) + 10
    assert language_priority("ja", ("en",)) is None


# ── get_platform_subtitles with mocked fetch_text ──────────────────────


def test_get_platform_subtitles_priority(monkeypatch):
    """Bilibili platform picks zh-CN over en when both are available."""
    zh_json = json.dumps({"body": [{"from": 0.0, "to": 1.0, "content": "中文"}]})
    en_json = json.dumps({"body": [{"from": 0.0, "to": 1.0, "content": "english"}]})

    def _fake_subtitle_map(url: str) -> str:
        if "lang=zh-Hans" in url:
            return zh_json
        if "lang=en" in url:
            return en_json
        return '{"body": []}'

    import clipvault.subtitles as S
    monkeypatch.setattr(S, "fetch_text", _fake_subtitle_map)

    info = {
        "subtitles": {
            "zh-Hans": [{"url": "http://example.com/sub?lang=zh-Hans&ext=json", "ext": "json"}],
            "en": [{"url": "http://example.com/sub?lang=en&ext=json", "ext": "json"}],
        },
        "automatic_captions": {},
    }
    segments, source = S.get_platform_subtitles(info, platform="bilibili")
    assert len(segments) == 1
    assert "中文" in segments[0].text
    assert source.startswith("subtitle:zh-Hans")


def test_get_platform_subtitles_youtube_prefers_en(monkeypatch):
    """YouTube platform picks en over zh-CN when both are available."""
    zh_json = json.dumps({"body": [{"from": 0.0, "to": 1.0, "content": "中文"}]})
    en_json = json.dumps({"body": [{"from": 0.0, "to": 1.0, "content": "english"}]})

    def _fake_fetch(url: str) -> str:
        if "lang=en" in url:
            return en_json
        return zh_json

    import clipvault.subtitles as S
    monkeypatch.setattr(S, "fetch_text", _fake_fetch)

    info = {
        "subtitles": {
            "zh-Hans": [{"url": "http://example.com/sub?lang=zh-Hans&ext=json", "ext": "json"}],
            "en": [{"url": "http://example.com/sub?lang=en&ext=json", "ext": "json"}],
        },
        "automatic_captions": {},
    }
    segments, source = S.get_platform_subtitles(info, platform="youtube")
    assert len(segments) == 1
    assert "english" in segments[0].text
    assert source.startswith("subtitle:en")


def test_get_platform_subtitles_ext_priority(monkeypatch):
    """Within same language, json3 is preferred over vtt."""
    json3_data = json.dumps({"body": [{"from": 0.0, "to": 1.0, "content": "json3"}]})
    vtt_data = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nvtt"

    def _fake_fetch(url: str) -> str:
        if "ext=json3" in url:
            return json3_data
        return vtt_data

    import clipvault.subtitles as S
    monkeypatch.setattr(S, "fetch_text", _fake_fetch)

    info = {
        "subtitles": {
            "en": [
                {"url": "http://example.com/sub?ext=vtt", "ext": "vtt"},
                {"url": "http://example.com/sub?ext=json3", "ext": "json3"},
            ],
        },
        "automatic_captions": {},
    }
    segments, source = S.get_platform_subtitles(info, platform="youtube")
    assert len(segments) == 1
    assert "json3" in segments[0].text


def test_get_platform_subtitles_no_subtitles(monkeypatch):
    """When no subtitles match, returns empty list and 'none'."""
    info = {"subtitles": {}, "automatic_captions": {}}
    segments, source = get_platform_subtitles(info, platform="youtube")
    assert segments == []
    assert source == "none"
