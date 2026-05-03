from __future__ import annotations

import json
from pathlib import Path

from clipvault.library import (
    build_manifest,
    first_text,
    guess_platform,
    is_completed,
    legacy_video_directory,
    resolve_video_directory,
    safe_name,
    update_manifest,
    video_directory,
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


# --- video_directory ---


def test_video_directory_with_platform():
    path = video_directory(Path("/lib"), platform="bilibili", uploader="Creator", title="My Video", video_id="BV123")
    assert path == Path("/lib/bilibili/Creator/My Video - BV123")


def test_video_directory_sanitizes_names():
    path = video_directory(Path("/lib"), platform="youtube", uploader="Bad:Name", title="File/Path", video_id="x")
    assert "Bad_Name" in str(path)
    assert "File_Path" in str(path)


# --- legacy_video_directory ---


def test_legacy_video_directory():
    path = legacy_video_directory(Path("/lib"), uploader="Creator", title="Video", video_id="V1")
    assert path == Path("/lib/Creator/Video - V1")


# --- is_completed ---


def test_is_completed_true_when_subtitle_source_set(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"subtitle_source": "subtitle:en:json3"})
    assert is_completed(tmp_path)


def test_is_completed_false_when_no_manifest(tmp_path: Path):
    assert not is_completed(tmp_path)


def test_is_completed_false_when_subtitle_source_null(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"subtitle_source": None})
    assert not is_completed(tmp_path)


def test_is_completed_false_when_subtitle_source_missing(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"title": "no source"})
    assert not is_completed(tmp_path)


def test_is_completed_false_on_corrupted_manifest(tmp_path: Path):
    (tmp_path / "manifest.json").write_text("not-json", encoding="utf-8")
    assert not is_completed(tmp_path)


def test_is_completed_legacy_manifest_with_output_files(tmp_path: Path):
    """A v0 manifest without subtitle_source is still completed if output files exist."""
    write_json(tmp_path / "manifest.json", {"url": "https://example.com", "title": "old"})
    (tmp_path / "transcript.srt").write_text("")
    (tmp_path / "transcript.txt").write_text("")
    (tmp_path / "transcript.md").write_text("")
    assert is_completed(tmp_path)


def test_is_completed_legacy_manifest_missing_output(tmp_path: Path):
    """A v0 manifest without output files should not be considered completed."""
    write_json(tmp_path / "manifest.json", {"url": "https://example.com", "title": "old"})
    assert not is_completed(tmp_path)


# --- resolve_video_directory ---


def test_resolve_prefers_new_path(tmp_path: Path):
    """When only the new platform-aware path has a completed manifest, prefer it."""
    new_dir = video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    new_dir.mkdir(parents=True)
    write_json(new_dir / "manifest.json", {"subtitle_source": "subtitle:en:json3"})

    result = resolve_video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    assert result == new_dir


def test_resolve_falls_back_to_legacy(tmp_path: Path):
    """When only the legacy path has a completed manifest, return it."""
    legacy_dir = legacy_video_directory(tmp_path, uploader="U", title="T", video_id="V1")
    legacy_dir.mkdir(parents=True)
    write_json(legacy_dir / "manifest.json", {"subtitle_source": "asr:faster-whisper"})

    result = resolve_video_directory(tmp_path, platform="youtube", uploader="U", title="T", video_id="V1")
    assert result == legacy_dir


def test_resolve_prefers_new_over_legacy_when_both_completed(tmp_path: Path):
    """When both paths have a completed manifest, prefer the new one."""
    new_dir = video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    new_dir.mkdir(parents=True)
    write_json(new_dir / "manifest.json", {"subtitle_source": "subtitle:en:json3"})

    legacy_dir = legacy_video_directory(tmp_path, uploader="U", title="T", video_id="V1")
    legacy_dir.mkdir(parents=True)
    write_json(legacy_dir / "manifest.json", {"subtitle_source": "asr:faster-whisper"})

    result = resolve_video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    assert result == new_dir


def test_resolve_returns_new_path_when_no_cache(tmp_path: Path):
    """When nothing is cached, return the new platform-aware path."""
    result = resolve_video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    expected = video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    assert result == expected
