from __future__ import annotations

import json
from pathlib import Path

from clipvault.library import (
    build_manifest,
    first_text,
    guess_platform,
    safe_name,
    update_manifest,
    write_json,
)


# --- guess_platform ---


def test_guess_platform_bilibili():
    assert guess_platform("https://www.bilibili.com/video/BV1xx") == "bilibili"
    assert guess_platform("https://b23.tv/abc123") == "bilibili"


def test_guess_platform_youtube():
    assert guess_platform("https://www.youtube.com/watch?v=abc") == "youtube"
    assert guess_platform("https://youtu.be/abc123") == "youtube"


def test_guess_platform_douyin():
    assert guess_platform("https://www.douyin.com/video/123") == "douyin"


def test_guess_platform_unknown():
    assert guess_platform("https://vimeo.com/12345") == "unknown"
    assert guess_platform("https://example.com/video") == "unknown"


# --- safe_name ---


def test_safe_name_removes_invalid_chars():
    assert safe_name('hello:world') == "hello_world"
    assert safe_name('file/name\\test') == "file_name_test"
    assert safe_name('a<b>c|d?e*f') == "a_b_c_d_e_f"


def test_safe_name_collapses_spaces():
    assert safe_name("hello   world") == "hello world"


def test_safe_name_strips_dots():
    assert safe_name(".hello .") == "hello"
    assert safe_name("hello.") == "hello"


def test_safe_name_empty_fallback():
    assert safe_name("") == "untitled"
    assert safe_name("   ") == "untitled"


def test_safe_name_truncates():
    long = "a" * 200
    assert len(safe_name(long)) <= 120


# --- first_text ---


def test_first_text_returns_first_matching():
    data = {"title": "Hello", "uploader": "World"}
    assert first_text(data, "title", default="nope") == "Hello"


def test_first_text_falls_through():
    data = {"title": "", "uploader": "World"}
    assert first_text(data, "title", "uploader", default="nope") == "World"


def test_first_text_default():
    assert first_text({}, "title", default="fallback") == "fallback"


def test_first_text_skips_none():
    data = {"title": None, "uploader": "Actual"}
    assert first_text(data, "title", "uploader", default="nope") == "Actual"


# --- write_json / update_manifest ---


def test_write_json_and_update(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, {"a": 1})
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data == {"a": 1}

    update_manifest(manifest_path, b=2, c=3)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data == {"a": 1, "b": 2, "c": 3}


# --- build_manifest ---


def test_build_manifest_schema_version():
    info = {}
    manifest = build_manifest(info, url="https://example.com", title="T", uploader="U", video_id="V")
    assert manifest["schema_version"] == 1
    assert manifest["title"] == "T"
    assert manifest["uploader"] == "U"
    assert manifest["video_id"] == "V"
    assert manifest["source_url"] == "https://example.com"
    assert manifest["platform"] == "unknown"


def test_build_manifest_platform_detection():
    info = {}
    manifest = build_manifest(info, url="https://www.bilibili.com/video/BV1xx", title="T", uploader="U", video_id="V")
    assert manifest["platform"] == "bilibili"


def test_build_manifest_nullable_fields():
    info = {"duration": 120, "upload_date": "20260101", "description": "desc"}
    manifest = build_manifest(info, url="https://example.com", title="T", uploader="U", video_id="V")
    assert manifest["duration"] == 120
    assert manifest["upload_date"] == "20260101"
    assert manifest["description"] == "desc"
    assert manifest["subtitle_source"] is None
    assert manifest["asr_model"] is None
    assert manifest["asr_device"] is None
    assert manifest["output_files"] == []
