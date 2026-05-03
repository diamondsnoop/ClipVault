from __future__ import annotations

import json
from pathlib import Path

from clipvault.subtitles import SubtitleSegment


def test_process_video_with_series(tmp_path: Path, monkeypatch):
    """Verify --series flows into output path and manifest."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")

    def fake_extract_info(url: str, *, verbose: bool):
        return {
            "title": "Test Video",
            "uploader": "Test Creator",
            "id": "test123",
            "duration": 60,
            "upload_date": "20260101",
            "description": "A test video",
            "channel_id": "UCtest",
            "webpage_url": "https://www.youtube.com/watch?v=test123",
        }

    monkeypatch.setattr("clipvault.cli.extract_info", fake_extract_info)

    segments = [SubtitleSegment(0.0, 1.0, "hello")]
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform: (segments, "subtitle:en:json3"),
    )

    from clipvault.cli import process_video

    result = process_video(
        url="https://www.youtube.com/watch?v=test123",
        library=tmp_path,
        model_name="tiny",
        device="cpu",
        compute_type="int8",
        force=True,
        keep_audio=False,
        verbose=False,
        series="Test Series",
    )

    # Check output path contains series directory
    assert "Test Series" in result["folder"]
    assert result["folder"].endswith("Test Series/Test Video - test123") or result["folder"].endswith("Test Series\\Test Video - test123")

    # Check manifest contains series field
    manifest_path = Path(result["folder"]) / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["series"] == "Test Series"
    assert manifest["subtitle_source"] == "subtitle:en:json3"

    # Check result fields
    assert result["platform"] == "youtube"
    assert result["status"] == "ok"


def test_process_video_without_series(tmp_path: Path, monkeypatch):
    """Without --series, manifest has series: null and path is unchanged."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")

    def fake_extract_info(url: str, *, verbose: bool):
        return {
            "title": "Test Video",
            "uploader": "Test Creator",
            "id": "test456",
        }

    monkeypatch.setattr("clipvault.cli.extract_info", fake_extract_info)

    segments = [SubtitleSegment(0.0, 1.0, "hello")]
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform: (segments, "subtitle:en:json3"),
    )

    from clipvault.cli import process_video

    result = process_video(
        url="https://www.youtube.com/watch?v=test456",
        library=tmp_path,
        model_name="tiny",
        device="cpu",
        compute_type="int8",
        force=True,
        keep_audio=False,
        verbose=False,
        series=None,
    )

    manifest_path = Path(result["folder"]) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["series"] is None
    # Path should NOT contain a series segment
    assert "Test Series" not in result["folder"]


def test_process_video_stripped_series(tmp_path: Path, monkeypatch):
    """series=' Test Series ' is stripped, path uses 'Test Series', manifest writes 'Test Series'."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose: {"title": "T", "uploader": "U", "id": "id1"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
    )

    from clipvault.cli import process_video

    result = process_video(
        url="https://youtube.com/watch?v=id1",
        library=tmp_path,
        model_name="tiny", device="cpu", compute_type="int8",
        force=True, keep_audio=False, verbose=False,
        series="  Test Series  ",
    )
    assert "Test Series" in result["folder"]
    manifest = json.loads((Path(result["folder"]) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["series"] == "Test Series"


def test_process_video_blank_series_equals_no_series(tmp_path: Path, monkeypatch):
    """series='   ' creates no series dir and manifest series is None."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose: {"title": "T", "uploader": "U", "id": "id2"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
    )

    from clipvault.cli import process_video

    result = process_video(
        url="https://youtube.com/watch?v=id2",
        library=tmp_path,
        model_name="tiny", device="cpu", compute_type="int8",
        force=True, keep_audio=False, verbose=False,
        series="   ",
    )
    # No untitled series directory
    assert "untitled" not in result["folder"]
    manifest = json.loads((Path(result["folder"]) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["series"] is None


def test_process_video_cache_hit_creates_index(tmp_path: Path, monkeypatch):
    """Cache hit without pre-existing index still creates indexes."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose: {"title": "T", "uploader": "U", "id": "vid1", "channel_id": "UCx"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
    )

    from clipvault.cli import process_video

    # First run — creates outputs and index
    r1 = process_video(
        url="https://youtube.com/watch?v=vid1",
        library=tmp_path,
        model_name="tiny", device="cpu", compute_type="int8",
        force=True, keep_audio=False, verbose=False,
        series="Cache Series",
    )
    assert r1["status"] == "ok"

    # Remove index files to simulate pre-index cache
    import shutil
    c_path = tmp_path / "youtube" / "U" / "_index.json"
    s_path = tmp_path / "youtube" / "U" / "Cache Series" / "_index.json"
    assert c_path.exists()
    assert s_path.exists()
    c_path.unlink()
    s_path.unlink()

    # Second run without --force — cache hit
    r2 = process_video(
        url="https://youtube.com/watch?v=vid1",
        library=tmp_path,
        model_name="tiny", device="cpu", compute_type="int8",
        force=False, keep_audio=False, verbose=False,
        series="Cache Series",
    )
    assert r2["status"] == "cached"

    # Indexes should have been recreated on cache hit
    assert c_path.exists()
    assert s_path.exists()
    c_data = json.loads(c_path.read_text(encoding="utf-8"))
    assert len(c_data["videos"]) == 1
    assert c_data["videos"][0]["video_id"] == "vid1"
    s_data = json.loads(s_path.read_text(encoding="utf-8"))
    assert len(s_data["videos"]) == 1
    assert s_data["videos"][0]["video_id"] == "vid1"


# ── Auto series rules (Phase 4 Step 3) ─────────────────────────────────


def test_process_video_auto_series_via_rule(tmp_path: Path, monkeypatch):
    """Without --series, a rules-based match assigns series automatically."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose: {"title": "My Great Video", "uploader": "U", "id": "vid1"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
    )
    monkeypatch.setattr(
        "clipvault.cli.resolve_series",
        lambda library, *, platform, uploader, title, explicit_series: ("Auto Series", "rule"),
    )

    from clipvault.cli import process_video

    result = process_video(
        url="https://youtube.com/watch?v=vid1",
        library=tmp_path,
        model_name="tiny", device="cpu", compute_type="int8",
        force=True, keep_audio=False, verbose=False,
        series=None,
    )
    assert result["status"] == "ok"
    assert result["series"] == "Auto Series"
    assert result["series_source"] == "rule"
    assert "Auto Series" in result["folder"]

    manifest_path = Path(result["folder"]) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["series"] == "Auto Series"


def test_process_video_manual_series_overrides_rule(tmp_path: Path, monkeypatch):
    """--series takes priority even when auto-rules would match."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose: {"title": "My Great Video", "uploader": "U", "id": "vid2"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
    )
    # resolve_series should be called with explicit_series="Manual" and return manual
    monkeypatch.setattr(
        "clipvault.cli.resolve_series",
        lambda library, *, platform, uploader, title, explicit_series: ("Manual", "manual"),
    )

    from clipvault.cli import process_video

    result = process_video(
        url="https://youtube.com/watch?v=vid2",
        library=tmp_path,
        model_name="tiny", device="cpu", compute_type="int8",
        force=True, keep_audio=False, verbose=False,
        series="Manual",
    )
    assert result["status"] == "ok"
    assert result["series"] == "Manual"
    assert result["series_source"] == "manual"
    assert "Manual" in result["folder"]


def test_process_video_no_series_no_rules(tmp_path: Path, monkeypatch):
    """Without --series and no rules match, series is null."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose: {"title": "Plain Video", "uploader": "U", "id": "vid3"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
    )
    monkeypatch.setattr(
        "clipvault.cli.resolve_series",
        lambda library, *, platform, uploader, title, explicit_series: (None, None),
    )

    from clipvault.cli import process_video

    result = process_video(
        url="https://youtube.com/watch?v=vid3",
        library=tmp_path,
        model_name="tiny", device="cpu", compute_type="int8",
        force=True, keep_audio=False, verbose=False,
        series=None,
    )
    assert result["status"] == "ok"
    assert result["series"] is None
    assert result["series_source"] is None
    # No series directory: video folder is directly under creator dir
    assert Path(result["folder"]).parent.name == "U"


def test_process_video_cache_hit_auto_series(tmp_path: Path, monkeypatch):
    """Cache hit with auto-series still returns series info and updates indexes."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose: {"title": "Cached Video", "uploader": "U", "id": "vid4"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
    )

    auto_resolve = lambda library, *, platform, uploader, title, explicit_series: ("Auto Series", "rule")  # noqa: E731

    from clipvault.cli import process_video

    # First run creates cached entry with auto series
    monkeypatch.setattr(
        "clipvault.cli.resolve_series",
        auto_resolve,
    )
    r1 = process_video(
        url="https://youtube.com/watch?v=vid4",
        library=tmp_path,
        model_name="tiny", device="cpu", compute_type="int8",
        force=True, keep_audio=False, verbose=False,
        series=None,
    )
    assert r1["status"] == "ok"
    assert r1["series"] == "Auto Series"

    # Second run without --force — cache hit
    r2 = process_video(
        url="https://youtube.com/watch?v=vid4",
        library=tmp_path,
        model_name="tiny", device="cpu", compute_type="int8",
        force=False, keep_audio=False, verbose=False,
        series=None,
    )
    assert r2["status"] == "cached"
    assert r2["series"] == "Auto Series"
    assert r2["series_source"] == "rule"
    # Indexes exist
    c_path = tmp_path / "youtube" / "U" / "_index.json"
    assert c_path.exists()
    c_data = json.loads(c_path.read_text(encoding="utf-8"))
    assert len(c_data["videos"]) == 1
    assert c_data["videos"][0]["video_id"] == "vid4"


# ── Library maintenance CLI ───────────────────────────────────────────


def test_process_library_rebuild_index_command(tmp_path: Path):
    from clipvault.cli import process_library_command
    from clipvault.library import video_directory, write_json

    video_dir = video_directory(tmp_path, platform="youtube", uploader="U", title="T", video_id="v1")
    video_dir.mkdir(parents=True)
    write_json(
        video_dir / "manifest.json",
        {
            "schema_version": 1,
            "title": "T",
            "uploader": "U",
            "video_id": "v1",
            "source_url": "https://youtube.com/watch?v=v1",
            "platform": "youtube",
            "series": None,
            "processed_at": "2026-01-01T00:00:00+00:00",
            "subtitle_source": "subtitle:en:json3",
            "output_files": ["transcript.srt", "transcript.txt", "transcript.md"],
        },
    )
    (video_dir / "transcript.srt").write_text("", encoding="utf-8")
    (video_dir / "transcript.txt").write_text("", encoding="utf-8")
    (video_dir / "transcript.md").write_text("", encoding="utf-8")

    result = process_library_command(["rebuild-index", "--library", str(tmp_path)])

    assert result["status"] == "ok"
    assert result["videos_indexed"] == 1
    assert (tmp_path / "youtube" / "U" / "_index.json").exists()


def test_process_library_rebuild_index_dry_run(tmp_path: Path):
    from clipvault.cli import process_library_command

    result = process_library_command(["rebuild-index", "--library", str(tmp_path), "--dry-run"])

    assert result["status"] == "ok"
    assert result["dry_run"] is True
