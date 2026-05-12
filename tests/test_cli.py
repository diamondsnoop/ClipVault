from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from clipvault.asr import TranscriptionResult
from clipvault.subtitles import SubtitleSegment

AUTH_SENTINEL = "__clipvault_auth__"


def _parse_cli(raw_args: list[str]):
    from clipvault.cli import _normalize_legacy_args, build_parser

    return build_parser().parse_args(_normalize_legacy_args(raw_args))


def test_top_level_help_discovers_subcommands():
    from clipvault.cli import build_parser

    help_text = build_parser().format_help()

    assert "video" in help_text
    assert "library" in help_text
    assert "creator" in help_text
    assert "queue" in help_text
    assert "auth" in help_text
    assert "ui" in help_text


def test_ui_command_parses():
    args = _parse_cli(["ui", "--port", "9090", "--no-open"])

    assert args.command == "ui"
    assert args.port == 9090
    assert args.no_open is True


def test_auth_subcommand_not_normalized():
    from clipvault.cli import _normalize_legacy_args

    args = ["auth", "login", "--platform", "bilibili"]
    assert _normalize_legacy_args(args) == args


def test_legacy_video_args_are_normalized():
    from clipvault.cli import _normalize_legacy_args

    assert _normalize_legacy_args(["https://youtube.com/watch?v=x"])[0] == "video"
    assert _normalize_legacy_args(["--model", "tiny", "https://youtube.com/watch?v=x"])[0] == "video"
    assert _normalize_legacy_args(["--help"]) == ["--help"]


def test_global_library_before_subcommand_is_preserved():
    from clipvault.cli import _normalize_legacy_args

    args = ["--library", "E:\\VideoSubs", "library", "rebuild-index"]
    assert _normalize_legacy_args(args) == args


def test_global_cookies_before_subcommand_is_preserved():
    from clipvault.cli import _normalize_legacy_args

    args = ["--cookies", "creator", "fetch", "闲木鱼"]
    assert _normalize_legacy_args(args) == ["--cookies=__clipvault_auth__", "creator", "fetch", "闲木鱼"]


def test_global_cookies_before_subcommand_parses_as_stored_credentials():
    args = _parse_cli(["--cookies", "creator", "fetch", "闲木鱼"])

    assert args.command == "creator"
    assert args.creator_command == "fetch"
    assert args.selector == "闲木鱼"
    assert args.cookies == AUTH_SENTINEL


def test_global_cookies_path_before_subcommand_parses_as_cookie_file():
    args = _parse_cli(["--cookies", ".secrets/bilibili-cookies.txt", "creator", "fetch", "闲木鱼"])

    assert args.command == "creator"
    assert args.creator_command == "fetch"
    assert args.selector == "闲木鱼"
    assert args.cookies == ".secrets/bilibili-cookies.txt"


def test_global_cookies_auto_auth_not_normalized():
    from clipvault.cli import _normalize_legacy_args

    args = ["--cookies", "auth", "list"]
    assert _normalize_legacy_args(args) == ["--cookies=__clipvault_auth__", "auth", "list"]


def test_global_cookies_bare_url_normalizes():
    from clipvault.cli import _normalize_legacy_args

    args = ["--cookies", "https://www.bilibili.com/video/BV1xx"]
    result = _normalize_legacy_args(args)
    assert result == ["--cookies=__clipvault_auth__", "video", "https://www.bilibili.com/video/BV1xx"]


def test_global_cookies_bare_url_parses_as_stored_credentials():
    args = _parse_cli(["--cookies", "https://www.bilibili.com/video/BV1xx"])

    assert args.command == "video"
    assert args.url == "https://www.bilibili.com/video/BV1xx"
    assert args.cookies == AUTH_SENTINEL


def test_video_cookies_before_url_parses_as_stored_credentials():
    args = _parse_cli(["video", "--cookies", "https://www.bilibili.com/video/BV1xx"])

    assert args.command == "video"
    assert args.url == "https://www.bilibili.com/video/BV1xx"
    assert args.cookies == AUTH_SENTINEL


def test_process_video_with_series(tmp_path: Path, monkeypatch):
    """Verify --series flows into output path and manifest."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")

    def fake_extract_info(url: str, *, verbose: bool, cookies=None):
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
        lambda info, platform, cookies=None: (segments, "subtitle:en:json3"),
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

    def fake_extract_info(url: str, *, verbose: bool, cookies=None):
        return {
            "title": "Test Video",
            "uploader": "Test Creator",
            "id": "test456",
        }

    monkeypatch.setattr("clipvault.cli.extract_info", fake_extract_info)

    segments = [SubtitleSegment(0.0, 1.0, "hello")]
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: (segments, "subtitle:en:json3"),
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


def test_process_video_passes_cookies_to_fetchers(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    seen: dict[str, object] = {}

    def fake_extract_info(url: str, *, verbose: bool, cookies=None):
        seen["metadata"] = cookies
        return {
            "title": "Test Video",
            "uploader": "Test Creator",
            "id": "test789",
        }

    def fake_get_subtitles(info, *, platform: str, cookies=None):
        seen["subtitles"] = cookies
        return [SubtitleSegment(0.0, 1.0, "hello")], "subtitle:zh-CN:json"

    monkeypatch.setattr("clipvault.cli.extract_info", fake_extract_info)
    monkeypatch.setattr("clipvault.cli.get_platform_subtitles", fake_get_subtitles)

    from clipvault.cli import process_video

    result = process_video(
        url="https://www.bilibili.com/video/BV1xx",
        library=tmp_path,
        model_name="tiny",
        device="cpu",
        compute_type="int8",
        force=True,
        keep_audio=False,
        verbose=False,
        series=None,
        cookies=True,
    )

    assert result["status"] == "ok"
    assert seen == {"metadata": True, "subtitles": True}


def test_process_video_manifest_update_failure_does_not_abort(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose, cookies=None: {"title": "T", "uploader": "U", "id": "vid-manifest"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
    )
    monkeypatch.setattr("clipvault.cli.update_manifest", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    seen = {"index_called": False}

    def fake_update_library_indexes(video_dir, manifest, library):
        seen["index_called"] = True

    monkeypatch.setattr("clipvault.cli.update_library_indexes", fake_update_library_indexes)

    from clipvault.cli import process_video

    result = process_video(
        url="https://youtube.com/watch?v=vid-manifest",
        library=tmp_path,
        model_name="tiny",
        device="cpu",
        compute_type="int8",
        force=True,
        keep_audio=False,
        verbose=False,
    )

    assert result["status"] == "ok"
    assert seen["index_called"] is False


def test_process_video_asr_simplifies_chinese_output(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose, cookies=None: {"title": "T", "uploader": "U", "id": "vid-asr"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([], "none"),
    )

    audio_path = tmp_path / "audio.m4a"
    audio_path.write_text("x", encoding="utf-8")
    monkeypatch.setattr("clipvault.cli.download_audio", lambda *args, **kwargs: audio_path)
    monkeypatch.setattr(
        "clipvault.cli.transcribe_audio",
        lambda *args, **kwargs: [SubtitleSegment(0.0, 1.0, "學習 繁體 中文")],
    )
    monkeypatch.setattr(
        "clipvault.cli.simplify_chinese_segments",
        lambda segments: [SubtitleSegment(0.0, 1.0, "学习 简体 中文")],
    )

    from clipvault.cli import process_video

    result = process_video(
        url="https://www.bilibili.com/video/BV1asr",
        library=tmp_path,
        model_name="tiny",
        device="cpu",
        compute_type="int8",
        force=True,
        keep_audio=False,
        verbose=False,
    )

    transcript_txt = Path(result["folder"]) / "transcript.txt"
    assert "学习 简体 中文" in transcript_txt.read_text(encoding="utf-8")
    assert result["source"] == "asr:faster-whisper"


def test_process_video_asr_simplify_failure_is_non_blocking(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose, cookies=None: {"title": "T", "uploader": "U", "id": "vid-asr-warn"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([], "none"),
    )

    audio_path = tmp_path / "audio.m4a"
    audio_path.write_text("x", encoding="utf-8")
    monkeypatch.setattr("clipvault.cli.download_audio", lambda *args, **kwargs: audio_path)
    monkeypatch.setattr(
        "clipvault.cli.transcribe_audio",
        lambda *args, **kwargs: [SubtitleSegment(0.0, 1.0, "學習 繁體 中文")],
    )
    monkeypatch.setattr(
        "clipvault.cli.simplify_chinese_segments",
        lambda segments: (_ for _ in ()).throw(RuntimeError("缺少 opencc")),
    )

    from clipvault.cli import process_video

    result = process_video(
        url="https://www.bilibili.com/video/BV1warn",
        library=tmp_path,
        model_name="tiny",
        device="cpu",
        compute_type="int8",
        force=True,
        keep_audio=False,
        verbose=False,
    )

    transcript_txt = Path(result["folder"]) / "transcript.txt"
    assert "學習 繁體 中文" in transcript_txt.read_text(encoding="utf-8")
    assert result["status"] == "ok"


def test_process_video_records_actual_asr_device(monkeypatch):
    tmp_path = Path.cwd() / ".tmp" / "test-cli" / f"case-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose, cookies=None: {"title": "T", "uploader": "U", "id": "vid-asr-device"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([], "none"),
    )

    audio_path = tmp_path / "audio.m4a"
    audio_path.write_text("x", encoding="utf-8")
    monkeypatch.setattr("clipvault.cli.download_audio", lambda *args, **kwargs: audio_path)
    monkeypatch.setattr(
        "clipvault.cli.transcribe_audio",
        lambda *args, **kwargs: TranscriptionResult(
            segments=[SubtitleSegment(0.0, 1.0, "cpu fallback")],
            device="cpu",
            compute_type="int8",
        ),
    )

    from clipvault.cli import process_video

    try:
        result = process_video(
            url="https://www.bilibili.com/video/BV1cpu",
            library=tmp_path,
            model_name="tiny",
            device="auto",
            compute_type="auto",
            force=True,
            keep_audio=False,
            verbose=False,
        )

        manifest_path = Path(result["folder"]) / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert result["asr_device"] == "cpu"
        assert manifest["asr_device"] == "cpu"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_process_video_stripped_series(tmp_path: Path, monkeypatch):
    """series=' Test Series ' is stripped, path uses 'Test Series', manifest writes 'Test Series'."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "clipvault.cli.extract_info",
        lambda url, *, verbose, cookies=None: {"title": "T", "uploader": "U", "id": "id1"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
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
        lambda url, *, verbose, cookies=None: {"title": "T", "uploader": "U", "id": "id2"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
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
        lambda url, *, verbose, cookies=None: {"title": "T", "uploader": "U", "id": "vid1", "channel_id": "UCx"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
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
        lambda url, *, verbose, cookies=None: {"title": "My Great Video", "uploader": "U", "id": "vid1"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
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
        lambda url, *, verbose, cookies=None: {"title": "My Great Video", "uploader": "U", "id": "vid2"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
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
        lambda url, *, verbose, cookies=None: {"title": "Plain Video", "uploader": "U", "id": "vid3"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
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
        lambda url, *, verbose, cookies=None: {"title": "Cached Video", "uploader": "U", "id": "vid4"},
    )
    monkeypatch.setattr(
        "clipvault.cli.get_platform_subtitles",
        lambda info, platform, cookies=None: ([SubtitleSegment(0.0, 1.0, "h")], "subtitle:en:json3"),
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


# ── Creator tracking CLI ──────────────────────────────────────────────


def test_process_creator_add_command(tmp_path: Path):
    from clipvault.cli import process_creator_command

    result = process_creator_command([
        "add",
        "https://www.youtube.com/@Jabzy",
        "--name",
        "Jabzy",
        "--library",
        str(tmp_path),
    ])

    assert result["status"] == "ok"
    assert result["creator"]["platform"] == "youtube"
    assert result["creator"]["name"] == "Jabzy"
    assert (tmp_path / "_creators.json").exists()


def test_process_creator_list_command(tmp_path: Path):
    from clipvault.cli import process_creator_command

    process_creator_command([
        "add",
        "https://www.youtube.com/@Jabzy",
        "--name",
        "Jabzy",
        "--library",
        str(tmp_path),
    ])

    result = process_creator_command(["list", "--library", str(tmp_path)])

    assert result["status"] == "ok"
    assert len(result["creators"]) == 1
    assert result["creators"][0]["name"] == "Jabzy"


def test_process_creator_fetch_command(tmp_path: Path, monkeypatch):
    from clipvault.cli import process_creator_command

    process_creator_command([
        "add",
        "https://www.youtube.com/@Jabzy",
        "--name",
        "Jabzy",
        "--library",
        str(tmp_path),
    ])
    monkeypatch.setattr(
        "clipvault.creators.extract_creator_entries",
        lambda url, *, limit, verbose, cookies=None: [{"id": "v1", "title": "One", "url": "https://youtube.com/watch?v=v1"}],
    )

    result = process_creator_command(["fetch", "Jabzy", "--limit", "1", "--library", str(tmp_path)])

    assert result["status"] == "ok"
    assert result["mode"] == "preview"
    assert result["count"] == 1


def test_process_creator_fetch_command_passes_cookies(tmp_path: Path, monkeypatch):
    from clipvault.cli import process_creator_command

    process_creator_command([
        "add",
        "https://www.bilibili.com/video/BV1xx",
        "--name",
        "Bili",
        "--library",
        str(tmp_path),
    ])
    seen: dict[str, object] = {}

    def fake_extract_creator_entries(url, *, limit, verbose, cookies=None):
        seen["cookies"] = cookies
        return [{"id": "BV1", "title": "One", "url": "https://www.bilibili.com/video/BV1"}]

    monkeypatch.setattr("clipvault.creators.extract_creator_entries", fake_extract_creator_entries)

    result = process_creator_command([
        "fetch", "Bili",
        "--limit", "1",
        "--library", str(tmp_path),
        "--cookies",
    ])

    assert result["status"] == "ok"
    assert seen["cookies"] == "__clipvault_auth__"


def test_process_creator_enqueue_command(tmp_path: Path, monkeypatch):
    from clipvault.cli import process_creator_command

    process_creator_command([
        "add",
        "https://www.youtube.com/@Jabzy",
        "--name",
        "Jabzy",
        "--library",
        str(tmp_path),
    ])
    monkeypatch.setattr(
        "clipvault.creators.extract_creator_entries",
        lambda url, *, limit, verbose, cookies=None: [{"id": "v1", "title": "One", "url": "https://youtube.com/watch?v=v1"}],
    )

    result = process_creator_command(["enqueue", "Jabzy", "--limit", "1", "--library", str(tmp_path)])

    assert result["status"] == "ok"
    assert result["added_count"] == 1
    assert (tmp_path / "_queue.json").exists()


# ── Queue CLI ─────────────────────────────────────────────────────────


def test_process_queue_list_and_status_commands(tmp_path: Path):
    from clipvault.cli import process_queue_command
    from clipvault.creators import write_job_queue

    write_job_queue(
        tmp_path,
        {
            "jobs": [
                {"id": "one", "status": "pending", "source_url": "https://youtube.com/watch?v=1"},
                {"id": "two", "status": "done", "source_url": "https://youtube.com/watch?v=2"},
            ],
        },
    )

    listed = process_queue_command(["list", "--library", str(tmp_path), "--status", "pending"])
    status = process_queue_command(["status", "--library", str(tmp_path)])

    assert [job["id"] for job in listed["jobs"]] == ["one"]
    assert status["counts"] == {"pending": 1, "done": 1}


def test_process_queue_run_command(tmp_path: Path, monkeypatch):
    from clipvault.cli import process_queue_command
    from clipvault.creators import load_job_queue, write_job_queue

    write_job_queue(
        tmp_path,
        {
            "jobs": [
                {"id": "one", "status": "pending", "source_url": "https://youtube.com/watch?v=1"},
            ],
        },
    )
    monkeypatch.setattr(
        "clipvault.cli.process_video",
        lambda **kwargs: {
            "status": "ok",
            "folder": str(tmp_path / "out"),
            "markdown": str(tmp_path / "out" / "transcript.md"),
            "source": "subtitle:en:json3",
        },
    )

    result = process_queue_command(["run", "--library", str(tmp_path)])

    assert result["processed_count"] == 1
    assert result["succeeded_count"] == 1
    queue = load_job_queue(tmp_path)
    assert queue["jobs"][0]["status"] == "done"
    assert queue["jobs"][0]["result"]["source"] == "subtitle:en:json3"


def test_process_queue_run_passes_cookies(tmp_path: Path, monkeypatch):
    from clipvault.cli import process_queue_command
    from clipvault.creators import write_job_queue

    write_job_queue(
        tmp_path,
        {
            "jobs": [
                {"id": "one", "status": "pending", "source_url": "https://www.bilibili.com/video/BV1"},
            ],
        },
    )
    seen: dict[str, object] = {}

    def fake_process_video(**kwargs):
        seen["cookies"] = kwargs.get("cookies")
        return {
            "status": "ok",
            "folder": str(tmp_path / "out"),
            "markdown": str(tmp_path / "out" / "transcript.md"),
            "source": "subtitle:zh-CN:json",
        }

    monkeypatch.setattr("clipvault.cli.process_video", fake_process_video)

    result = process_queue_command(["run", "--library", str(tmp_path), "--cookies"])

    assert result["succeeded_count"] == 1
    assert seen["cookies"] == "__clipvault_auth__"


def test_process_queue_run_records_failure(tmp_path: Path, monkeypatch):
    from clipvault.cli import process_queue_command
    from clipvault.creators import load_job_queue, write_job_queue

    write_job_queue(
        tmp_path,
        {
            "jobs": [
                {"id": "bad", "status": "pending", "source_url": "https://youtube.com/watch?v=bad"},
            ],
        },
    )

    def fail_process_video(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("clipvault.cli.process_video", fail_process_video)

    result = process_queue_command(["run", "--library", str(tmp_path)])

    assert result["failed_count"] == 1
    queue = load_job_queue(tmp_path)
    assert queue["jobs"][0]["status"] == "failed"
    assert queue["jobs"][0]["last_error"] == "boom"
