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
