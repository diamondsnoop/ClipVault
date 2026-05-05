from __future__ import annotations

import json
from pathlib import Path

from clipvault.library import (
    build_manifest,
    creator_index_path,
    first_text,
    guess_platform,
    is_completed,
    legacy_video_directory,
    normalize_series,
    rebuild_library_indexes,
    resolve_video_directory,
    safe_name,
    series_index_path,
    update_library_indexes,
    update_manifest,
    video_directory,
    write_json,
)


# --- guess_platform ---


def test_guess_platform_bilibili():
    assert guess_platform("https://www.bilibili.com/video/BV1xx") == "bilibili"
    assert guess_platform("https://b23.tv/abc123") == "bilibili"


def test_guess_platform_rejects_fake_domains():
    """Verifies guess_platform (which delegates to identify_platform)
    does not match substring-hosting domains."""
    assert guess_platform("https://notyoutube.com/watch?v=x") == "unknown"
    assert guess_platform("https://evilbilibili.com/video/BV1") == "unknown"


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


# --- normalize_series ---


def test_normalize_series_none():
    assert normalize_series(None) is None


def test_normalize_series_empty():
    assert normalize_series("") is None


def test_normalize_series_whitespace():
    assert normalize_series("   ") is None
    assert normalize_series("\t\n") is None


def test_normalize_series_strips():
    assert normalize_series(" 睡前消息 ") == "睡前消息"
    assert normalize_series("  Series Name  ") == "Series Name"


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


def test_build_manifest_series():
    manifest = build_manifest({}, url="https://example.com", title="T", uploader="U", video_id="V", series="睡前消息")
    assert manifest["series"] == "睡前消息"


def test_build_manifest_series_none():
    manifest = build_manifest({}, url="https://example.com", title="T", uploader="U", video_id="V")
    assert manifest["series"] is None


def test_build_manifest_blank_series_is_none():
    """Blank series in build_manifest is stored as None (normalized before call)."""
    manifest = build_manifest({}, url="https://example.com", title="T", uploader="U", video_id="V", series="   ")
    assert manifest["series"] is None


# --- video_directory ---


def test_video_directory_with_platform():
    path = video_directory(Path("/lib"), platform="bilibili", uploader="Creator", title="My Video", video_id="BV123")
    assert path == Path("/lib/bilibili/Creator/My Video - BV123")


def test_video_directory_sanitizes_names():
    path = video_directory(Path("/lib"), platform="youtube", uploader="Bad:Name", title="File/Path", video_id="x")
    assert "Bad_Name" in str(path)
    assert "File_Path" in str(path)


def test_video_directory_with_series():
    path = video_directory(Path("/lib"), platform="bilibili", uploader="Creator", title="Title", video_id="BV1", series="睡前消息")
    assert path == Path("/lib/bilibili/Creator/睡前消息/Title - BV1")


def test_video_directory_series_sanitized():
    path = video_directory(Path("/lib"), platform="bilibili", uploader="Creator", title="Title", video_id="BV1", series="A/B: C")
    assert "A_B_ C" in str(path)
    assert "/lib/bilibili/Creator/A_B_ C/Title - BV1" in str(path).replace("\\", "/")


def test_video_directory_series_none_is_unchanged():
    """Explicit series=None produces same path as omitting series."""
    with_series = video_directory(Path("/lib"), platform="bilibili", uploader="Creator", title="Title", video_id="BV1", series=None)
    without = video_directory(Path("/lib"), platform="bilibili", uploader="Creator", title="Title", video_id="BV1")
    assert with_series == without
    assert with_series == Path("/lib/bilibili/Creator/Title - BV1")


def test_video_directory_blank_series_equals_no_series():
    """Blank series should not create an 'untitled' series directory."""
    blank = video_directory(Path("/lib"), platform="bilibili", uploader="Creator", title="Title", video_id="BV1", series="   ")
    no_series = video_directory(Path("/lib"), platform="bilibili", uploader="Creator", title="Title", video_id="BV1")
    assert blank == no_series
    assert "untitled" not in str(blank)


# --- legacy_video_directory ---


def test_legacy_video_directory():
    path = legacy_video_directory(Path("/lib"), uploader="Creator", title="Video", video_id="V1")
    assert path == Path("/lib/Creator/Video - V1")


# --- is_completed ---


def test_is_completed_true_when_manifest_outputs_exist(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    write_json(
        manifest,
        {
            "subtitle_source": "subtitle:en:json3",
            "output_files": ["transcript.srt", "transcript.txt", "transcript.md"],
        },
    )
    (tmp_path / "transcript.srt").write_text("", encoding="utf-8")
    (tmp_path / "transcript.txt").write_text("", encoding="utf-8")
    (tmp_path / "transcript.md").write_text("", encoding="utf-8")
    assert is_completed(tmp_path)


def test_is_completed_false_when_manifest_output_missing(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    write_json(
        manifest,
        {
            "subtitle_source": "subtitle:en:json3",
            "output_files": ["transcript.srt", "transcript.txt", "transcript.md"],
        },
    )
    (tmp_path / "transcript.srt").write_text("", encoding="utf-8")
    (tmp_path / "transcript.txt").write_text("", encoding="utf-8")
    assert not is_completed(tmp_path)


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
    (new_dir / "transcript.srt").write_text("", encoding="utf-8")
    (new_dir / "transcript.txt").write_text("", encoding="utf-8")
    (new_dir / "transcript.md").write_text("", encoding="utf-8")

    result = resolve_video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    assert result == new_dir


def test_resolve_falls_back_to_legacy(tmp_path: Path):
    """When only the legacy path has a completed manifest, return it."""
    legacy_dir = legacy_video_directory(tmp_path, uploader="U", title="T", video_id="V1")
    legacy_dir.mkdir(parents=True)
    write_json(legacy_dir / "manifest.json", {"subtitle_source": "asr:faster-whisper"})
    (legacy_dir / "transcript.srt").write_text("", encoding="utf-8")
    (legacy_dir / "transcript.txt").write_text("", encoding="utf-8")
    (legacy_dir / "transcript.md").write_text("", encoding="utf-8")

    result = resolve_video_directory(tmp_path, platform="youtube", uploader="U", title="T", video_id="V1")
    assert result == legacy_dir


def test_resolve_prefers_new_over_legacy_when_both_completed(tmp_path: Path):
    """When both paths have a completed manifest, prefer the new one."""
    new_dir = video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    new_dir.mkdir(parents=True)
    write_json(new_dir / "manifest.json", {"subtitle_source": "subtitle:en:json3"})
    (new_dir / "transcript.srt").write_text("", encoding="utf-8")
    (new_dir / "transcript.txt").write_text("", encoding="utf-8")
    (new_dir / "transcript.md").write_text("", encoding="utf-8")

    legacy_dir = legacy_video_directory(tmp_path, uploader="U", title="T", video_id="V1")
    legacy_dir.mkdir(parents=True)
    write_json(legacy_dir / "manifest.json", {"subtitle_source": "asr:faster-whisper"})
    (legacy_dir / "transcript.srt").write_text("", encoding="utf-8")
    (legacy_dir / "transcript.txt").write_text("", encoding="utf-8")
    (legacy_dir / "transcript.md").write_text("", encoding="utf-8")

    result = resolve_video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    assert result == new_dir


def test_resolve_returns_new_path_when_no_cache(tmp_path: Path):
    """When nothing is cached, return the new platform-aware path."""
    result = resolve_video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    expected = video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    assert result == expected


# --- resolve_video_directory with series ---


def test_resolve_with_series_returns_series_path(tmp_path: Path):
    """When series is provided, return series path (even if non-series cache exists)."""
    # Create a completed non-series path
    non_series = video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    non_series.mkdir(parents=True)
    write_json(non_series / "manifest.json", {"subtitle_source": "subtitle:en:json3"})
    (non_series / "transcript.srt").write_text("", encoding="utf-8")
    (non_series / "transcript.txt").write_text("", encoding="utf-8")
    (non_series / "transcript.md").write_text("", encoding="utf-8")

    # Series is requested but no series cache exists — must NOT return non-series path
    result = resolve_video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1", series="睡前消息")
    expected = video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1", series="睡前消息")
    assert result == expected
    assert result != non_series


def test_resolve_with_series_hits_series_cache(tmp_path: Path):
    """When series path has a completed manifest, return it."""
    series_dir = video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1", series="睡前消息")
    series_dir.mkdir(parents=True)
    write_json(series_dir / "manifest.json", {"subtitle_source": "subtitle:en:json3"})
    (series_dir / "transcript.srt").write_text("", encoding="utf-8")
    (series_dir / "transcript.txt").write_text("", encoding="utf-8")
    (series_dir / "transcript.md").write_text("", encoding="utf-8")

    result = resolve_video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1", series="睡前消息")
    assert result == series_dir


def test_resolve_no_series_still_hits_non_series_cache(tmp_path: Path):
    """Without series, existing non-series cache is still hit normally."""
    new_dir = video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    new_dir.mkdir(parents=True)
    write_json(new_dir / "manifest.json", {"subtitle_source": "subtitle:en:json3"})
    (new_dir / "transcript.srt").write_text("", encoding="utf-8")
    (new_dir / "transcript.txt").write_text("", encoding="utf-8")
    (new_dir / "transcript.md").write_text("", encoding="utf-8")

    result = resolve_video_directory(tmp_path, platform="bilibili", uploader="U", title="T", video_id="V1")
    assert result == new_dir


# ── Index path helpers ───────────────────────────────────────────────


def test_creator_index_path():
    path = creator_index_path(Path("/lib"), platform="youtube", uploader="Jabzy")
    assert path == Path("/lib/youtube/Jabzy/_index.json")


def test_series_index_path():
    path = series_index_path(Path("/lib"), platform="youtube", uploader="Jabzy", series="History of the Middle East")
    assert path == Path("/lib/youtube/Jabzy/History of the Middle East/_index.json")


def test_series_index_path_none():
    assert series_index_path(Path("/lib"), platform="youtube", uploader="Jabzy", series=None) is None
    assert series_index_path(Path("/lib"), platform="youtube", uploader="Jabzy", series="   ") is None


# ── update_library_indexes: creator index ────────────────────────────


def _make_manifest(*, video_id: str, title: str, uploader: str = "U", platform: str = "youtube", series: str | None = None, **kw: str) -> dict:
    from datetime import datetime, timezone
    m = {
        "schema_version": 1,
        "title": title,
        "uploader": uploader,
        "video_id": video_id,
        "source_url": f"https://youtube.com/watch?v={video_id}",
        "webpage_url": f"https://youtube.com/watch?v={video_id}",
        "platform": platform,
        "series": normalize_series(series),
        "duration": 120,
        "upload_date": "20260101",
        "description": "",
        "creator_id": "UCtest",
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "subtitle_source": "subtitle:en:json3",
        "asr_model": None,
        "asr_device": None,
        "output_files": ["transcript.srt", "transcript.txt", "transcript.md"],
    }
    m.update(kw)
    return m


def _write_completed_video(
    library: Path,
    *,
    video_id: str,
    title: str,
    uploader: str = "U",
    platform: str = "youtube",
    series: str | None = None,
    **kw: str,
) -> Path:
    video_dir = video_directory(library, platform=platform, uploader=uploader, title=title, video_id=video_id, series=series)
    video_dir.mkdir(parents=True)
    manifest = _make_manifest(video_id=video_id, title=title, uploader=uploader, platform=platform, series=series, **kw)
    write_json(video_dir / "manifest.json", manifest)
    (video_dir / "transcript.srt").write_text("", encoding="utf-8")
    (video_dir / "transcript.txt").write_text("", encoding="utf-8")
    (video_dir / "transcript.md").write_text("", encoding="utf-8")
    return video_dir


def test_creator_index_created_no_series(tmp_path: Path):
    """A video without series creates a creator _index.json."""
    video_dir = video_directory(tmp_path, platform="youtube", uploader="Jabzy", title="Video One", video_id="v1")
    video_dir.mkdir(parents=True)
    manifest = _make_manifest(video_id="v1", title="Video One", uploader="Jabzy", series=None)
    update_library_indexes(video_dir, manifest, tmp_path)

    c_path = creator_index_path(tmp_path, platform="youtube", uploader="Jabzy")
    assert c_path.exists()

    data = json.loads(c_path.read_text(encoding="utf-8"))
    assert data["type"] == "creator"
    assert data["creator"] == "Jabzy"
    assert len(data["videos"]) == 1
    assert data["videos"][0]["video_id"] == "v1"
    assert data["videos"][0]["series"] is None
    # relative_path is just the folder name for non-series
    assert "/" not in data["videos"][0]["relative_path"]


def test_creator_index_with_series(tmp_path: Path):
    """A video with series creates a creator index with series info."""
    video_dir = video_directory(tmp_path, platform="youtube", uploader="Jabzy", title="Video Two", video_id="v2", series="睡前消息")
    video_dir.mkdir(parents=True)
    manifest = _make_manifest(video_id="v2", title="Video Two", uploader="Jabzy", series="睡前消息")
    update_library_indexes(video_dir, manifest, tmp_path)

    c_path = creator_index_path(tmp_path, platform="youtube", uploader="Jabzy")
    data = json.loads(c_path.read_text(encoding="utf-8"))

    assert len(data["videos"]) == 1
    assert data["videos"][0]["video_id"] == "v2"
    assert data["videos"][0]["series"] == "睡前消息"
    # relative_path contains series folder
    assert "睡前消息" in data["videos"][0]["relative_path"]

    # Series aggregation is populated
    assert len(data["series"]) == 1
    assert data["series"][0]["name"] == "睡前消息"
    assert data["series"][0]["video_count"] == 1


def test_creator_index_dedup(tmp_path: Path):
    """Re-processing same video_id overwrites, does not append."""
    video_dir = video_directory(tmp_path, platform="youtube", uploader="U", title="Original", video_id="v1")
    video_dir.mkdir(parents=True)
    m1 = _make_manifest(video_id="v1", title="Original", uploader="U")
    update_library_indexes(video_dir, m1, tmp_path)

    # "Re-process": same video_id, different title
    m2 = _make_manifest(video_id="v1", title="Updated", uploader="U")
    update_library_indexes(video_dir, m2, tmp_path)

    c_path = creator_index_path(tmp_path, platform="youtube", uploader="U")
    data = json.loads(c_path.read_text(encoding="utf-8"))
    assert len(data["videos"]) == 1  # not 2
    assert data["videos"][0]["title"] == "Updated"


def test_creator_index_no_absolute_path(tmp_path: Path):
    """relative_path in creator index must not be an absolute path."""
    video_dir = video_directory(tmp_path, platform="youtube", uploader="Jabzy", title="Video", video_id="v1")
    video_dir.mkdir(parents=True)
    manifest = _make_manifest(video_id="v1", title="Video", uploader="Jabzy", series="Series")
    update_library_indexes(video_dir, manifest, tmp_path)

    c_path = creator_index_path(tmp_path, platform="youtube", uploader="Jabzy")
    data = json.loads(c_path.read_text(encoding="utf-8"))
    for v in data["videos"]:
        assert not Path(v["relative_path"]).is_absolute()


# ── update_library_indexes: series index ─────────────────────────────


def test_series_index_created(tmp_path: Path):
    """video with series creates series _index.json."""
    video_dir = video_directory(tmp_path, platform="youtube", uploader="Jabzy", title="Video", video_id="v1", series="Series")
    video_dir.mkdir(parents=True)
    manifest = _make_manifest(video_id="v1", title="Video", uploader="Jabzy", series="Series")
    update_library_indexes(video_dir, manifest, tmp_path)

    s_path = series_index_path(tmp_path, platform="youtube", uploader="Jabzy", series="Series")
    assert s_path is not None
    assert s_path.exists()

    data = json.loads(s_path.read_text(encoding="utf-8"))
    assert data["type"] == "series"
    assert data["series"] == "Series"
    assert data["video_count"] == 1
    assert len(data["videos"]) == 1
    assert data["videos"][0]["video_id"] == "v1"
    # Series index relative_path is just the video folder, no series prefix
    assert "/" not in data["videos"][0]["relative_path"]


def test_series_index_not_created_without_series(tmp_path: Path):
    """No series → no series _index.json."""
    video_dir = video_directory(tmp_path, platform="youtube", uploader="Jabzy", title="Video", video_id="v1")
    video_dir.mkdir(parents=True)
    manifest = _make_manifest(video_id="v1", title="Video", uploader="Jabzy", series=None)
    update_library_indexes(video_dir, manifest, tmp_path)

    s_path = series_index_path(tmp_path, platform="youtube", uploader="Jabzy", series="Any")
    if s_path is not None:
        assert not s_path.exists()


def test_series_index_blank_series_no_index(tmp_path: Path):
    """--series '   ' is treated as no series, no series index created."""
    video_dir = video_directory(tmp_path, platform="youtube", uploader="Jabzy", title="Video", video_id="v1")
    video_dir.mkdir(parents=True)
    manifest = _make_manifest(video_id="v1", title="Video", uploader="Jabzy", series="   ")
    update_library_indexes(video_dir, manifest, tmp_path)

    s_path = series_index_path(tmp_path, platform="youtube", uploader="Jabzy", series="   ")
    assert s_path is None


def test_series_index_video_count(tmp_path: Path):
    """Multiple videos in same series increments video_count."""
    for vid, title in [("v1", "Alpha"), ("v2", "Beta")]:
        video_dir = video_directory(tmp_path, platform="youtube", uploader="U", title=title, video_id=vid, series="Series")
        video_dir.mkdir(parents=True)
        manifest = _make_manifest(video_id=vid, title=title, uploader="U", series="Series")
        update_library_indexes(video_dir, manifest, tmp_path)

    s_path = series_index_path(tmp_path, platform="youtube", uploader="U", series="Series")
    assert s_path is not None
    data = json.loads(s_path.read_text(encoding="utf-8"))
    assert data["video_count"] == 2
    assert len(data["videos"]) == 2


def test_series_index_stripped_series(tmp_path: Path):
    """--series '  Test Series  ' writes 'Test Series' to index."""
    video_dir = video_directory(tmp_path, platform="youtube", uploader="U", title="Video", video_id="v1", series="  Test Series  ")
    video_dir.mkdir(parents=True)
    manifest = _make_manifest(video_id="v1", title="Video", uploader="U", series="  Test Series  ")
    update_library_indexes(video_dir, manifest, tmp_path)

    # Creator index should show normalized name
    c_path = creator_index_path(tmp_path, platform="youtube", uploader="U")
    c_data = json.loads(c_path.read_text(encoding="utf-8"))
    assert c_data["videos"][0]["series"] == "Test Series"

    # Series index should be at safe_name path with normalized name
    s_path = series_index_path(tmp_path, platform="youtube", uploader="U", series="Test Series")
    assert s_path is not None
    assert s_path.exists()
    s_data = json.loads(s_path.read_text(encoding="utf-8"))
    assert s_data["series"] == "Test Series"


# ── Creator index: series aggregation (no null) ────────────────────────


def test_creator_index_no_series_agg_empty(tmp_path: Path):
    """No-series video: series aggregation is empty, video entry has series: null."""
    video_dir = video_directory(tmp_path, platform="youtube", uploader="U", title="Video", video_id="v1")
    video_dir.mkdir(parents=True)
    manifest = _make_manifest(video_id="v1", title="Video", uploader="U", series=None)
    update_library_indexes(video_dir, manifest, tmp_path)

    c_path = creator_index_path(tmp_path, platform="youtube", uploader="U")
    data = json.loads(c_path.read_text(encoding="utf-8"))
    assert data["videos"][0]["series"] is None
    assert data["series"] == []


def test_creator_index_mixed_series_agg(tmp_path: Path):
    """Mix of series and no-series videos: only named series appear in aggregation."""
    for vid, title, series in [("v1", "Alpha", "S1"), ("v2", "Beta", None), ("v3", "Gamma", "S2")]:
        video_dir = video_directory(tmp_path, platform="youtube", uploader="U", title=title, video_id=vid, series=series)
        video_dir.mkdir(parents=True)
        manifest = _make_manifest(video_id=vid, title=title, uploader="U", series=series)
        update_library_indexes(video_dir, manifest, tmp_path)

    c_path = creator_index_path(tmp_path, platform="youtube", uploader="U")
    data = json.loads(c_path.read_text(encoding="utf-8"))

    # All 3 videos present
    assert len(data["videos"]) == 3
    # v2 has no series
    v2 = [v for v in data["videos"] if v["video_id"] == "v2"][0]
    assert v2["series"] is None
    # Series list only contains S1 and S2 (not null)
    names = {s["name"] for s in data["series"]}
    assert names == {"S1", "S2"}
    assert len(data["series"]) == 2


# ── Index sort order ────────────────────────────────────────────────────


def test_creator_index_sort_order(tmp_path: Path):
    """Sort: processed_at descending, then title ascending for same date."""
    for vid, title, date in [
        ("v1", "Zeta", "20260101"),
        ("v2", "Alpha", "20260101"),
        ("v3", "Beta", "20260102"),
    ]:
        video_dir = video_directory(tmp_path, platform="youtube", uploader="U", title=title, video_id=vid)
        video_dir.mkdir(parents=True)
        manifest = _make_manifest(video_id=vid, title=title, uploader="U", processed_at=f"{date}T00:00:00")
        update_library_indexes(video_dir, manifest, tmp_path)

    c_path = creator_index_path(tmp_path, platform="youtube", uploader="U")
    data = json.loads(c_path.read_text(encoding="utf-8"))

    # 20260102 comes first (descending)
    assert data["videos"][0]["video_id"] == "v3"  # Beta
    # 20260101: Alpha before Zeta (title ascending)
    assert data["videos"][1]["video_id"] == "v2"  # Alpha
    assert data["videos"][2]["video_id"] == "v1"  # Zeta


def test_series_index_sort_order(tmp_path: Path):
    """Series index also sorts: processed_at descending, then title ascending."""
    for vid, title, date in [
        ("v1", "Zeta", "20260101"),
        ("v2", "Alpha", "20260101"),
    ]:
        video_dir = video_directory(tmp_path, platform="youtube", uploader="U", title=title, video_id=vid, series="S")
        video_dir.mkdir(parents=True)
        manifest = _make_manifest(video_id=vid, title=title, uploader="U", series="S", processed_at=f"{date}T00:00:00")
        update_library_indexes(video_dir, manifest, tmp_path)

    s_path = series_index_path(tmp_path, platform="youtube", uploader="U", series="S")
    assert s_path is not None
    data = json.loads(s_path.read_text(encoding="utf-8"))
    # Same processed_at: Alpha before Zeta (title ascending)
    assert data["videos"][0]["video_id"] == "v2"  # Alpha
    assert data["videos"][1]["video_id"] == "v1"  # Zeta


# ── rebuild_library_indexes ───────────────────────────────────────────


def test_rebuild_indexes_empty_library(tmp_path: Path):
    result = rebuild_library_indexes(tmp_path)

    assert result["status"] == "ok"
    assert result["manifests_seen"] == 0
    assert result["videos_indexed"] == 0
    assert result["indexes"] == []


def test_rebuild_indexes_single_no_series(tmp_path: Path):
    _write_completed_video(tmp_path, video_id="v1", title="Video One", uploader="Jabzy", platform="youtube")

    result = rebuild_library_indexes(tmp_path)

    c_path = creator_index_path(tmp_path, platform="youtube", uploader="Jabzy")
    assert c_path.exists()
    data = json.loads(c_path.read_text(encoding="utf-8"))
    assert data["type"] == "creator"
    assert data["videos"][0]["video_id"] == "v1"
    assert data["videos"][0]["series"] is None
    assert data["series"] == []
    assert result["videos_indexed"] == 1
    assert not (tmp_path / "youtube" / "Jabzy" / "Any" / "_index.json").exists()


def test_rebuild_indexes_mixed_series_and_no_series(tmp_path: Path):
    _write_completed_video(tmp_path, video_id="v1", title="Alpha", uploader="U", series="S")
    _write_completed_video(tmp_path, video_id="v2", title="Beta", uploader="U", series=None)

    rebuild_library_indexes(tmp_path)

    c_path = creator_index_path(tmp_path, platform="youtube", uploader="U")
    c_data = json.loads(c_path.read_text(encoding="utf-8"))
    assert {v["video_id"] for v in c_data["videos"]} == {"v1", "v2"}
    assert c_data["series"] == [{"name": "S", "video_count": 1, "latest_processed_at": c_data["series"][0]["latest_processed_at"]}]

    s_path = series_index_path(tmp_path, platform="youtube", uploader="U", series="S")
    assert s_path is not None
    s_data = json.loads(s_path.read_text(encoding="utf-8"))
    assert [v["video_id"] for v in s_data["videos"]] == ["v1"]


def test_rebuild_indexes_multiple_platforms_and_creators(tmp_path: Path):
    _write_completed_video(tmp_path, video_id="yt1", title="YT", uploader="A", platform="youtube")
    _write_completed_video(tmp_path, video_id="bv1", title="BV", uploader="A", platform="bilibili")
    _write_completed_video(tmp_path, video_id="yt2", title="Other", uploader="B", platform="youtube")

    rebuild_library_indexes(tmp_path)

    assert (tmp_path / "youtube" / "A" / "_index.json").exists()
    assert (tmp_path / "bilibili" / "A" / "_index.json").exists()
    assert (tmp_path / "youtube" / "B" / "_index.json").exists()
    yt_a = json.loads((tmp_path / "youtube" / "A" / "_index.json").read_text(encoding="utf-8"))
    assert [v["video_id"] for v in yt_a["videos"]] == ["yt1"]


def test_rebuild_indexes_removes_stale_index_entries(tmp_path: Path):
    stale_dir = _write_completed_video(tmp_path, video_id="stale", title="Stale", uploader="U")
    keep_dir = _write_completed_video(tmp_path, video_id="keep", title="Keep", uploader="U")
    rebuild_library_indexes(tmp_path)
    (stale_dir / "manifest.json").unlink()

    rebuild_library_indexes(tmp_path)

    c_data = json.loads((tmp_path / "youtube" / "U" / "_index.json").read_text(encoding="utf-8"))
    assert [v["video_id"] for v in c_data["videos"]] == ["keep"]
    assert keep_dir.exists()


def test_rebuild_indexes_deduplicates_video_id(tmp_path: Path):
    _write_completed_video(tmp_path, video_id="dup", title="First", uploader="U")
    _write_completed_video(tmp_path, video_id="dup", title="Second", uploader="U")

    rebuild_library_indexes(tmp_path)

    c_data = json.loads((tmp_path / "youtube" / "U" / "_index.json").read_text(encoding="utf-8"))
    assert len(c_data["videos"]) == 1
    assert c_data["videos"][0]["video_id"] == "dup"

    result = rebuild_library_indexes(tmp_path)
    assert result["videos_indexed"] == 1


def test_rebuild_indexes_removes_stale_index_file(tmp_path: Path):
    _write_completed_video(tmp_path, video_id="v1", title="Series Video", uploader="U", series="Old Series")
    rebuild_library_indexes(tmp_path)
    s_path = tmp_path / "youtube" / "U" / "Old Series" / "_index.json"
    assert s_path.exists()
    (tmp_path / "youtube" / "U" / "Old Series" / "Series Video - v1" / "manifest.json").unlink()

    result = rebuild_library_indexes(tmp_path)

    assert not s_path.exists()
    assert str(s_path) in result["stale_indexes"]


def test_rebuild_indexes_skips_bad_manifest(tmp_path: Path, capsys):
    bad_dir = tmp_path / "youtube" / "U" / "Bad - bad"
    bad_dir.mkdir(parents=True)
    (bad_dir / "manifest.json").write_text("{bad", encoding="utf-8")
    _write_completed_video(tmp_path, video_id="good", title="Good", uploader="U")

    result = rebuild_library_indexes(tmp_path)

    stderr = capsys.readouterr().err
    assert "skipped manifest" in stderr
    assert len(result["skipped_manifests"]) == 1
    c_data = json.loads((tmp_path / "youtube" / "U" / "_index.json").read_text(encoding="utf-8"))
    assert [v["video_id"] for v in c_data["videos"]] == ["good"]


def test_rebuild_indexes_skips_manifest_missing_video_id(tmp_path: Path, capsys):
    video_dir = tmp_path / "youtube" / "U" / "Missing - id"
    video_dir.mkdir(parents=True)
    write_json(
        video_dir / "manifest.json",
        {
            "schema_version": 1,
            "platform": "youtube",
            "uploader": "U",
            "title": "Missing",
            "subtitle_source": "subtitle:en:json3",
            "output_files": ["transcript.srt", "transcript.txt", "transcript.md"],
        },
    )
    (video_dir / "transcript.srt").write_text("", encoding="utf-8")
    (video_dir / "transcript.txt").write_text("", encoding="utf-8")
    (video_dir / "transcript.md").write_text("", encoding="utf-8")

    result = rebuild_library_indexes(tmp_path)

    assert result["videos_indexed"] == 0
    assert "missing required field: video_id" in capsys.readouterr().err
    assert not (tmp_path / "youtube" / "U" / "_index.json").exists()


def test_rebuild_indexes_dry_run_does_not_write(tmp_path: Path):
    _write_completed_video(tmp_path, video_id="v1", title="Video", uploader="U")

    result = rebuild_library_indexes(tmp_path, dry_run=True)

    assert result["dry_run"] is True
    assert result["indexes"]
    assert not (tmp_path / "youtube" / "U" / "_index.json").exists()
