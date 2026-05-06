from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from clipvault.ui import server


def _write_video(
    library: Path,
    *,
    platform: str = "youtube",
    uploader: str = "Jabzy",
    title: str = "Video",
    video_id: str = "v1",
    series: str | None = None,
) -> Path:
    parts = [library, platform, uploader]
    if series:
        parts.append(series)
    parts.append(f"{title} - {video_id}")
    video_dir = Path(*parts)
    video_dir.mkdir(parents=True)
    manifest = {
        "title": title,
        "uploader": uploader,
        "video_id": video_id,
        "platform": platform,
        "series": series,
        "subtitle_source": "subtitle:en:json3",
        "duration": 60,
        "upload_date": "20260101",
        "processed_at": f"2026-01-01T00:00:0{video_id[-1]}Z",
    }
    (video_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (video_dir / "transcript.md").write_text("# transcript", encoding="utf-8")
    return video_dir


def test_scan_library_tree_includes_series_videos(tmp_path: Path):
    direct = _write_video(tmp_path, title="Direct", video_id="v1")
    series_video = _write_video(tmp_path, title="Series Video", video_id="v2", series="History")
    (series_video.parent / "_index.json").write_text("{}", encoding="utf-8")

    tree = server._scan_library_tree(tmp_path)

    creator = tree[0]["creators"][0]
    assert creator["video_count"] == 2
    assert creator["videos"][0]["relative_path"] == str(direct.relative_to(tmp_path))
    assert creator["series"][0]["name"] == "History"
    assert creator["series"][0]["video_count"] == 1
    assert creator["series"][0]["videos"][0]["relative_path"] == str(series_video.relative_to(tmp_path))


def test_path_is_within_root_rejects_prefix_escape(tmp_path: Path):
    root = tmp_path / "lib"
    root.mkdir()
    outside = tmp_path / "library-evil" / "file.txt"
    outside.parent.mkdir()
    outside.write_text("x", encoding="utf-8")

    assert server.path_is_within_root(root / "inside.txt", root)
    assert not server.path_is_within_root(outside, root)


def test_configured_library_root_uses_saved_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings_file = tmp_path / "settings.json"
    selected = tmp_path / "selected-library"
    monkeypatch.setattr(server, "settings_path", lambda: settings_file)

    server.save_settings({
        "library": str(selected),
        "model": "small",
        "device": "auto",
        "compute_type": "auto",
        "cookies": None,
    })

    assert server.configured_library_root(tmp_path / "fallback") == selected.resolve()


def test_build_queue_run_command_includes_runtime_options(tmp_path: Path):
    settings = {
        "model": "small",
        "device": "cuda",
        "compute_type": "float16",
        "cookies": ".secrets/cookies.txt",
    }

    cmd = server.build_queue_run_command(tmp_path, settings, {"limit": 2, "retry_failed": True})

    assert cmd[:4] == [sys.executable, "-m", "clipvault", "queue"]
    assert cmd[4] == "run"
    assert ["--library", str(tmp_path)] == [cmd[5], cmd[6]]
    assert "--retry-failed" in cmd
    assert ["--cookies", ".secrets/cookies.txt"] == cmd[-2:]


def test_build_queue_run_command_rejects_bad_limit(tmp_path: Path):
    with pytest.raises(ValueError, match="limit must be at least 1"):
        server.build_queue_run_command(tmp_path, {}, {"limit": 0})
