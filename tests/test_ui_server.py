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
        "simplify_chinese": True,
        "cookies": None,
    })

    assert server.configured_library_root(tmp_path / "fallback") == selected.resolve()


def test_build_queue_run_command_includes_runtime_options(tmp_path: Path):
    settings = {
        "model": "small",
        "device": "cuda",
        "compute_type": "float16",
        "simplify_chinese": True,
        "cookies": ".secrets/cookies.txt",
    }

    cmd = server.build_queue_run_command(tmp_path, settings, {"limit": 2, "retry_failed": True})

    assert cmd[:4] == [sys.executable, "-m", "clipvault", "queue"]
    assert cmd[4] == "run"
    assert ["--library", str(tmp_path)] == [cmd[5], cmd[6]]
    assert "--retry-failed" in cmd
    assert ["--cookies", ".secrets/cookies.txt"] == cmd[-2:]


def test_build_queue_run_command_rejects_bad_limit(tmp_path: Path):
    with pytest.raises(ValueError, match="limit 至少为 1"):
        server.build_queue_run_command(tmp_path, {}, {"limit": 0})


def test_build_queue_run_command_can_disable_chinese_simplification(tmp_path: Path):
    settings = {
        "model": "small",
        "device": "cuda",
        "compute_type": "float16",
        "simplify_chinese": True,
        "cookies": None,
    }

    cmd = server.build_queue_run_command(tmp_path, settings, {"limit": 1, "simplify_chinese": False})

    assert "--no-simplify-chinese" in cmd


def test_job_run_persists_failure_logs_and_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings_file = tmp_path / "config" / "settings.json"
    monkeypatch.setattr(server, "settings_path", lambda: settings_file)

    code = (
        "import sys\n"
        "sys.stderr.write('[错误][ASR] CUDA 转写失败\\n')\n"
        "sys.exit(1)\n"
    )
    job = server.Job("jobfail01", "video", [sys.executable, "-c", code])

    manager = server.JobManager()
    manager._run(job)

    assert job.status == "failed"
    assert "CUDA 转写失败" in (job.error or "")
    assert "退出码 1" in (job.error or "")
    assert job.log_dir is not None
    assert (job.log_dir / "stderr.log").read_text(encoding="utf-8") == "[错误][ASR] CUDA 转写失败\n"
    assert (job.log_dir / "stdout.txt").read_text(encoding="utf-8") == ""

    snapshot = json.loads((job.log_dir / "job.json").read_text(encoding="utf-8"))
    assert snapshot["status"] == "failed"
    assert snapshot["error"] == job.error
    assert snapshot["log_dir"] == str(job.log_dir)
    assert snapshot["log_files"]["stderr"] == str(job.log_dir / "stderr.log")


def test_prepare_job_logging_creates_snapshot_before_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings_file = tmp_path / "config" / "settings.json"
    monkeypatch.setattr(server, "settings_path", lambda: settings_file)

    job = server.Job("jobprep01", "video", [sys.executable, "-c", "print('ok')"])

    server._prepare_job_logging(job)

    assert job.log_dir is not None
    snapshot = json.loads((job.log_dir / "job.json").read_text(encoding="utf-8"))
    assert snapshot["job_id"] == "jobprep01"
    assert snapshot["status"] == "queued"
    assert snapshot["log_dir"] == str(job.log_dir)
    assert snapshot["log_files"]["job"] == str(job.log_dir / "job.json")


def test_prepare_job_logging_falls_back_when_default_root_is_unwritable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    blocked = tmp_path / "blocked-root"
    blocked.write_text("x", encoding="utf-8")
    monkeypatch.setattr(server, "jobs_root_path", lambda: blocked)

    fallback_root = tmp_path / "library" / "_job_logs"
    job = server.Job("jobprep02", "video", [sys.executable, "-c", "print('ok')"], log_root=fallback_root)

    server._prepare_job_logging(job)

    assert job.log_dir is not None
    assert job.log_dir.parent == fallback_root
    assert any("默认日志目录不可用" in line for line in job.events)


def test_job_run_persists_success_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings_file = tmp_path / "config" / "settings.json"
    monkeypatch.setattr(server, "settings_path", lambda: settings_file)

    code = (
        "import json, sys\n"
        "sys.stderr.write('[流程] 处理开始\\n')\n"
        "print(json.dumps({'status': 'ok', 'source': 'subtitle:test', 'segments': 3}, ensure_ascii=False))\n"
    )
    job = server.Job("jobsucc01", "video", [sys.executable, "-c", code])

    manager = server.JobManager()
    manager._run(job)

    assert job.status == "succeeded"
    assert job.result == {"status": "ok", "source": "subtitle:test", "segments": 3}
    assert job.log_dir is not None
    assert json.loads((job.log_dir / "result.json").read_text(encoding="utf-8")) == job.result
    assert "subtitle:test" in (job.log_dir / "stdout.txt").read_text(encoding="utf-8")

    snapshot = json.loads((job.log_dir / "job.json").read_text(encoding="utf-8"))
    assert snapshot["status"] == "succeeded"
    assert snapshot["result"] == job.result


def test_job_run_accepts_progress_lines_before_json_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings_file = tmp_path / "config" / "settings.json"
    monkeypatch.setattr(server, "settings_path", lambda: settings_file)

    code = (
        "import json\n"
        "print('[download] 100% of 44.90MiB')\n"
        "print(json.dumps({'status': 'ok', 'source': 'asr:faster-whisper', 'segments': 3}, ensure_ascii=False, indent=2))\n"
    )
    job = server.Job("jobsucc02", "video", [sys.executable, "-c", code])

    manager = server.JobManager()
    manager._run(job)

    assert job.status == "succeeded"
    assert job.result == {"status": "ok", "source": "asr:faster-whisper", "segments": 3}
    assert job.log_dir is not None
    assert json.loads((job.log_dir / "result.json").read_text(encoding="utf-8")) == job.result
