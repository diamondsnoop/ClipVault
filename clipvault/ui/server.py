from __future__ import annotations

import http.server
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from clipvault.runtime_logs import emit_log

DEFAULT_PORT = 8080
DEFAULT_HOST = "127.0.0.1"

# Lazy imports for backend functions
_creators: Any = None
_library: Any = None
JOB_ERROR_TAIL_LINES = 20


def _lazy_imports() -> None:
    global _creators, _library
    if _creators is None:
        from clipvault import creators as _c, library as _l
        _creators = _c
        _library = _l


# ── Job Manager ──────────────────────────────────────────────────────


class Job:
    __slots__ = ("job_id", "type", "status", "command", "events",
                 "result", "error", "returncode", "process",
                 "created_at", "started_at", "finished_at", "log_dir", "preferred_log_root", "error_context", "_lock", "_cond")

    def __init__(self, job_id: str, type: str, command: list[str], *, log_root: Path | None = None) -> None:
        self.job_id = job_id
        self.type = type
        self.status = "queued"
        self.command = command
        self.events: list[str] = []
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.returncode: int | None = None
        self.process: subprocess.Popen[str] | None = None
        self.created_at = time.time()
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.log_dir: Path | None = None
        self.preferred_log_root: Path | None = Path(log_root) if log_root is not None else None
        self.error_context: list[str] = []
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    def log_files(self) -> dict[str, str] | None:
        if self.log_dir is None:
            return None
        return {
            "job": str(self.log_dir / "job.json"),
            "stderr": str(self.log_dir / "stderr.log"),
            "stdout": str(self.log_dir / "stdout.txt"),
            "result": str(self.log_dir / "result.json"),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "type": self.type,
            "status": self.status,
            "command": " ".join(self.command) if isinstance(self.command, list) else self.command,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
            "error_context": self.error_context[-JOB_ERROR_TAIL_LINES:],
            "returncode": self.returncode,
            "log_dir": str(self.log_dir) if self.log_dir else None,
            "log_files": self.log_files(),
            "events": self.events[-500:],  # last 500 lines
        }


class JobManager:
    def __init__(self) -> None:
        self._job: Job | None = None
        self._lock = threading.Lock()

    def start(self, job: Job) -> bool:
        """Start a job. Returns False if another job is already running."""
        with self._lock:
            if self._job is not None and self._job.status == "running":
                return False
            self._job = job
        try:
            _prepare_job_logging(job)
        except OSError as exc:
            _append_job_event(job, f"[警告][界面] 创建任务日志目录失败：{exc}")
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return True

    def _run(self, job: Job) -> None:
        job.status = "running"
        job.started_at = time.time()
        stderr_log = None
        try:
            _prepare_job_logging(job)
            _write_job_snapshot(job)

            proc = subprocess.Popen(
                job.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            job.process = proc
            if job.log_dir is not None:
                stderr_log = (job.log_dir / "stderr.log").open("w", encoding="utf-8")

            # Read stderr line by line in real time
            def read_stderr() -> None:
                assert proc.stderr is not None
                for line in iter(proc.stderr.readline, ""):
                    if stderr_log is not None:
                        stderr_log.write(line)
                        stderr_log.flush()
                    _append_job_event(job, line)

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            # Read stdout (final JSON result) while stderr is streamed above.
            assert proc.stdout is not None
            stdout = proc.stdout.read()
            if job.log_dir is not None:
                (job.log_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
            proc.wait()
            stderr_thread.join()

            job.returncode = proc.returncode

            if proc.returncode == 0 and stdout:
                try:
                    job.result = json.loads(stdout)
                except json.JSONDecodeError as exc:
                    job.error = f"任务已结束，但返回结果不是有效 JSON：{exc}"
                    job.error_context = _stderr_tail(job.events)
                    job.status = "failed"
                else:
                    if job.log_dir is not None:
                        (job.log_dir / "result.json").write_text(
                            json.dumps(job.result, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                    job.status = "succeeded"
            elif proc.returncode == 0:
                job.status = "succeeded"
            else:
                job.error_context = _stderr_tail(job.events)
                job.error = _summarize_job_failure(stdout, job.error_context, proc.returncode)
                job.status = "failed"
        except Exception as exc:
            job.error = str(exc)
            job.error_context = _stderr_tail(job.events)
            job.status = "failed"
        finally:
            if stderr_log is not None:
                stderr_log.close()
            job.finished_at = time.time()
            _write_job_snapshot(job)
            with job._cond:
                job._cond.notify_all()

    def get_job(self) -> Job | None:
        with self._lock:
            return self._job

    def current_status(self) -> dict[str, Any]:
        with self._lock:
            if self._job is None:
                return {"status": "idle"}
            return self._job.to_dict()


_JOB_MANAGER = JobManager()


def settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ClipVault" / "settings.json"


def jobs_root_path() -> Path:
    return settings_path().parent / "jobs"


def workspace_jobs_root_path() -> Path:
    return Path.cwd() / ".tmp" / "jobs"


_settings_cache: dict[str, Any] | None = None


def _default_settings(fallback: Path) -> dict[str, Any]:
    return {
        "library": str(fallback),
        "model": "small",
        "device": "auto",
        "compute_type": "auto",
        "simplify_chinese": True,
        "cookies": None,
    }


def load_settings() -> dict[str, Any]:
    return load_settings_with_default()


def load_settings_with_default(default_library: Path | None = None) -> dict[str, Any]:
    global _settings_cache
    if _settings_cache is not None:
        return dict(_settings_cache)
    path = settings_path()
    fallback = default_library or (Path.cwd() / "library")
    defaults = _default_settings(fallback)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        _settings_cache = defaults
        return dict(defaults)
    if not isinstance(data, dict):
        _settings_cache = defaults
        return dict(defaults)
    defaults.update({k: v for k, v in data.items() if k in defaults})
    if not defaults.get("library"):
        defaults["library"] = str(fallback)
    _settings_cache = defaults
    return dict(defaults)


def invalidate_settings_cache() -> None:
    global _settings_cache
    _settings_cache = None


def save_settings(data: dict[str, Any]) -> None:
    global _settings_cache
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _settings_cache = dict(data)


def configured_library_root(fallback: Path) -> Path:
    raw = load_settings_with_default(fallback).get("library")
    if not raw:
        return fallback.resolve()
    return Path(str(raw)).expanduser().resolve()


def path_is_within_root(target_path: str | Path, root: Path) -> bool:
    try:
        Path(target_path).resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def build_queue_run_command(library_root: Path, settings: dict[str, Any], data: dict[str, Any]) -> list[str]:
    raw_limit = data.get("limit", 1)
    limit = int(raw_limit if raw_limit is not None else 1)
    if limit < 1:
        raise ValueError("limit 至少为 1")

    cmd = [
        sys.executable, "-m", "clipvault", "queue", "run",
        "--library", str(library_root),
        "--limit", str(limit),
        "--device", str(settings.get("device") or "auto"),
        "--model", str(settings.get("model") or "small"),
        "--compute-type", str(settings.get("compute_type") or "auto"),
    ]
    if data.get("retry_failed"):
        cmd.append("--retry-failed")
    if data.get("keep_audio"):
        cmd.append("--keep-audio")
    if data.get("verbose"):
        cmd.append("--verbose")
    simplify_chinese = _resolve_bool_option(data, settings, "simplify_chinese", True)
    if not simplify_chinese:
        cmd.append("--no-simplify-chinese")
    if settings.get("cookies"):
        cmd += ["--cookies", settings["cookies"]]
    return cmd


def _resolve_bool_option(data: dict[str, Any], settings: dict[str, Any], key: str, default: bool) -> bool:
    if key in data:
        return bool(data[key])
    return bool(settings.get(key, default))


def _append_job_event(job: Job, line: str) -> None:
    with job._cond:
        job.events.append(line.rstrip("\n"))
        job._cond.notify_all()


def _stderr_tail(events: list[str], *, limit: int = JOB_ERROR_TAIL_LINES) -> list[str]:
    return [line for line in events if str(line).strip()][-limit:]


def _summarize_job_failure(stdout: str, error_context: list[str], returncode: int | None) -> str:
    preferred = next((line for line in reversed(error_context) if "[错误]" in line), None)
    if preferred is None and error_context:
        preferred = error_context[-1]
    if preferred:
        return f"{preferred}（退出码 {returncode}）" if returncode is not None else preferred

    stdout_lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if stdout_lines:
        summary = stdout_lines[-1]
        return f"{summary}（退出码 {returncode}）" if returncode is not None else summary

    if returncode is None:
        return "任务失败。"
    return f"任务失败，退出码 {returncode}。"


def _job_directory_name(job: Job) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(job.created_at))
    millis = int((job.created_at - int(job.created_at)) * 1000)
    return f"{timestamp}-{millis:03d}-{job.type}-{job.job_id}"


def _job_log_root_candidates(job: Job) -> list[Path]:
    candidates = [jobs_root_path()]
    if job.preferred_log_root is not None:
        candidates.append(job.preferred_log_root)
    candidates.append(workspace_jobs_root_path())

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _create_job_log_dir(job: Job) -> Path:
    last_error: OSError | None = None
    for root in _job_log_root_candidates(job):
        try:
            root.mkdir(parents=True, exist_ok=True)
            path = root / _job_directory_name(job)
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise OSError("无法创建任务日志目录。")


def _prepare_job_logging(job: Job) -> None:
    if job.log_dir is None:
        job.log_dir = _create_job_log_dir(job)
        default_root = jobs_root_path()
        if job.log_dir.parent != default_root:
            _append_job_event(job, f"[警告][界面] 默认日志目录不可用，已回退到：{job.log_dir.parent}")
    _write_job_snapshot(job)


def _write_job_snapshot(job: Job) -> None:
    if job.log_dir is None:
        return
    snapshot_path = job.log_dir / "job.json"
    snapshot_path.write_text(
        json.dumps(job.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _job_done_payload(job: Job) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "returncode": job.returncode,
        "error": job.error,
        "error_context": job.error_context[-JOB_ERROR_TAIL_LINES:],
        "log_dir": str(job.log_dir) if job.log_dir else None,
        "log_files": job.log_files(),
    }


# ── Library Tree & Transcript ──────────────────────────────────────


def _scan_library_tree(library: Path) -> list[dict[str, Any]]:
    """Scan library directory and return a hierarchical tree of platforms/creators/series/videos."""
    tree: list[dict[str, Any]] = []
    if not library.is_dir():
        return tree
    try:
        entries = sorted(library.iterdir())
    except OSError:
        return tree

    for platform_dir in entries:
        if not platform_dir.is_dir() or platform_dir.name.startswith("_"):
            continue
        platform: dict[str, Any] = {
            "name": platform_dir.name,
            "type": "platform",
            "creators": [],
        }
        for creator_dir in sorted(platform_dir.iterdir()):
            if not creator_dir.is_dir():
                continue
            creator: dict[str, Any] = {
                "name": creator_dir.name,
                "type": "creator",
                "video_count": 0,
                "series": [],
                "videos": [],
            }
            for item in sorted(creator_dir.iterdir()):
                if not item.is_dir() or item.name.startswith("_"):
                    continue
                manifest_path = item / "manifest.json"
                if manifest_path.is_file():
                    video_entry = _video_entry_from_dir(library, item)
                    if video_entry:
                        creator["videos"].append(video_entry)
                else:
                    videos = _series_videos_from_dir(library, item)
                    series_entry = {
                        "name": item.name,
                        "type": "series",
                        "video_count": len(videos),
                        "videos": videos,
                    }
                    if videos:
                        creator["series"].append(series_entry)

            creator["series"].sort(key=lambda x: x["name"])
            creator["videos"].sort(key=lambda x: x.get("processed_at", "") or "", reverse=True)
            creator["video_count"] = len(creator["videos"]) + sum(
                len(series.get("videos", [])) for series in creator["series"]
            )
            if creator["series"] or creator["videos"]:
                platform["creators"].append(creator)

        if platform["creators"]:
            tree.append(platform)

    return tree


def _video_entry_from_dir(library: Path, video_dir: Path) -> dict[str, Any] | None:
    manifest_path = video_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {
        "name": video_dir.name,
        "type": "video",
        "title": manifest.get("title", video_dir.name),
        "video_id": manifest.get("video_id", ""),
        "platform": manifest.get("platform", ""),
        "uploader": manifest.get("uploader", ""),
        "subtitle_source": manifest.get("subtitle_source"),
        "duration": manifest.get("duration"),
        "upload_date": manifest.get("upload_date"),
        "processed_at": manifest.get("processed_at", ""),
        "series": manifest.get("series"),
        "relative_path": str(video_dir.relative_to(library)),
        "has_transcript": (video_dir / "transcript.md").is_file(),
    }


def _series_videos_from_dir(library: Path, series_dir: Path) -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []
    try:
        entries = sorted(series_dir.iterdir())
    except OSError:
        return videos
    for video_dir in entries:
        if not video_dir.is_dir() or video_dir.name.startswith("_"):
            continue
        video_entry = _video_entry_from_dir(library, video_dir)
        if video_entry:
            videos.append(video_entry)
    videos.sort(key=lambda x: x.get("processed_at", "") or "", reverse=True)
    return videos


def _read_transcript(video_path: Path) -> dict[str, Any]:
    for ext in ("md", "txt", "srt", "vtt"):
        file = video_path / f"transcript.{ext}"
        if file.is_file():
            try:
                content = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = file.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError:
                    content = file.read_text(encoding="latin-1")
            return {
                "has_transcript": True,
                "format": ext,
                "content": content[:100000],
                "size": len(content),
                "file_name": file.name,
            }
    return {"has_transcript": False}


class ClipVaultHandler(http.server.BaseHTTPRequestHandler):
    server_token: str = ""
    library_root: Path = Path.cwd() / "library"

    def log_message(self, format: str, *args: Any) -> None:
        emit_log("ui", f"{self.address_string()} - {format % args}")

    def _check_security(self) -> bool:
        host = self.headers.get("Host", "")
        if host and host.split(":")[0] not in ("127.0.0.1", "localhost"):
            self.send_error(403, "拒绝访问：Host 无效")
            return False
        origin = self.headers.get("Origin", "")
        if origin:
            parsed = urlparse(origin)
            if parsed.hostname not in ("127.0.0.1", "localhost"):
                self.send_error(403, "拒绝访问：Origin 无效")
                return False
        return True

    def _check_token(self) -> bool:
        token = self.headers.get("X-ClipVault-Token", "")
        if token != self.server_token:
            self.send_error(401, "未授权：token 缺失或无效")
            return False
        return True

    def _library_root(self) -> Path:
        return configured_library_root(self.library_root)

    def _validate_path_in_root(self, target_path: str) -> bool:
        return path_is_within_root(target_path, self._library_root())

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path: str) -> None:
        static_dir = Path(__file__).resolve().parent / "static"
        if path == "/" or path == "":
            path = "/index.html"
        file_path = (static_dir / path.lstrip("/")).resolve()
        try:
            file_path.relative_to(static_dir.resolve())
        except ValueError:
            self.send_error(403, "拒绝访问")
            return

        if not file_path.is_file():
            self.send_error(404, "未找到资源")
            return

        content = file_path.read_bytes()
        content_type = "text/html; charset=utf-8"
        if file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        if not self._check_security():
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path.startswith("/api/"):
            self._handle_api_get(path, parse_qs(parsed.query))
        else:
            self._serve_static(path)

    def do_POST(self) -> None:
        if not self._check_security() or not self._check_token():
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        data = json.loads(body) if body else {}
        self._handle_api_post(path, data)

    def _handle_api_get(self, path: str, params: dict[str, list[str]]) -> None:
        if path == "/api/status":
            self._send_json({"status": "ok", "version": "0.1.0"})
        elif path == "/api/settings":
            if not self._check_token():
                return
            self._send_json(load_settings_with_default(self.library_root))
        elif path == "/api/process/status":
            if not self._check_token():
                return
            self._send_json(_JOB_MANAGER.current_status())
        elif path == "/api/process/events":
            self._stream_events(params)
        elif path == "/api/library":
            if not self._check_token():
                return
            tree = _scan_library_tree(self._library_root())
            self._send_json({"status": "ok", "tree": tree})
        elif path == "/api/library/transcript":
            if not self._check_token():
                return
            rel_path = (params.get("path") or [""])[0]
            if not rel_path:
                self._send_json({"status": "error", "message": "缺少 path 参数。"}, 400)
                return
            target = str(self._library_root() / rel_path)
            if not self._validate_path_in_root(target):
                self._send_json({"status": "error", "message": "目标路径不在字幕库根目录内。"}, 403)
                return
            result = _read_transcript(Path(target))
            self._send_json(result)
        elif path == "/api/library/video":
            if not self._check_token():
                return
            rel_path = (params.get("path") or [""])[0]
            if not rel_path:
                self._send_json({"status": "error", "message": "缺少 path 参数。"}, 400)
                return
            target = str(self._library_root() / rel_path)
            if not self._validate_path_in_root(target):
                self._send_json({"status": "error", "message": "目标路径不在字幕库根目录内。"}, 403)
                return
            manifest_path = Path(target) / "manifest.json"
            if not manifest_path.is_file():
                self._send_json({"status": "error", "message": "没有找到 manifest.json。"}, 404)
                return
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._send_json(manifest)
            except Exception as exc:
                self._send_json({"status": "error", "message": str(exc)}, 500)
        elif path == "/api/creators":
            if not self._check_token():
                return
            _lazy_imports()
            creators = _creators.list_creator_sources(self._library_root())
            self._send_json({"status": "ok", "creators": creators})
        elif path == "/api/queue":
            if not self._check_token():
                return
            _lazy_imports()
            status = _creators.queue_status(self._library_root())
            jobs = _creators.list_queue_jobs(self._library_root())
            self._send_json({
                "status": "ok",
                "counts": status.get("counts", {}),
                "total": status.get("total", 0),
                "jobs": jobs,
            })
        else:
            self.send_error(404, "未找到 API")

    def _handle_api_post(self, path: str, data: dict[str, Any]) -> None:
        if path == "/api/settings":
            current = load_settings_with_default(self.library_root)
            updated = dict(current)
            for key in ("library", "model", "device", "compute_type", "simplify_chinese", "cookies"):
                if key in data:
                    updated[key] = data[key]
            if updated.get("library"):
                updated["library"] = str(Path(str(updated["library"])).expanduser().resolve())
            save_settings(updated)
            if updated.get("library"):
                self.__class__.library_root = Path(updated["library"])
            self._send_json({"status": "ok"})
        elif path == "/api/video":
            self._start_video_job(data)
        elif path == "/api/process/stop":
            self._stop_job()
        elif path == "/api/open-path":
            target = data.get("path", "")
            library_root = self._library_root()
            full_path = str((library_root / target).resolve()) if not os.path.isabs(target) else target
            if not self._validate_path_in_root(full_path):
                self._send_json({"status": "error", "message": "目标路径不在字幕库根目录内。"}, 403)
                return
            try:
                os.startfile(full_path)
            except AttributeError:
                import subprocess as _sp
                _sp.Popen(["open", full_path])
            self._send_json({"status": "ok"})
        elif path == "/api/library/rebuild-index":
            _lazy_imports()
            try:
                result = _library.rebuild_library_indexes(self._library_root(), dry_run=data.get("dry_run", False))
                self._send_json(result)
            except Exception as exc:
                self._send_json({"status": "error", "message": str(exc)}, 500)
        elif path == "/api/creators/add":
            _lazy_imports()
            source_url = data.get("source_url", "").strip()
            if not source_url:
                self._send_json({"status": "error", "message": "缺少 source_url。"}, 400)
                return
            try:
                result = _creators.add_creator_source(self._library_root(), source_url=source_url, name=data.get("name"))
                self._send_json({"status": "ok", "creator": result})
            except Exception as exc:
                self._send_json({"status": "error", "message": str(exc)}, 500)
        elif path == "/api/creators/fetch":
            _lazy_imports()
            selector = data.get("selector", "").strip()
            if not selector:
                self._send_json({"status": "error", "message": "缺少 selector。"}, 400)
                return
            settings = load_settings_with_default(self.library_root)
            cookies = settings.get("cookies")
            try:
                result = _creators.fetch_creator_videos(
                    self._library_root(),
                    selector=selector,
                    limit=data.get("limit", 10),
                    verbose=data.get("verbose", False),
                    cookies=cookies,
                )
                self._send_json(result)
            except Exception as exc:
                self._send_json({"status": "error", "message": str(exc)}, 500)
        elif path == "/api/creators/enqueue":
            _lazy_imports()
            selector = data.get("selector", "").strip()
            if not selector:
                self._send_json({"status": "error", "message": "缺少 selector。"}, 400)
                return
            settings = load_settings_with_default(self.library_root)
            cookies = settings.get("cookies")
            try:
                result = _creators.enqueue_creator_videos(
                    self._library_root(),
                    selector=selector,
                    limit=data.get("limit", 10),
                    verbose=data.get("verbose", False),
                    cookies=cookies,
                )
                self._send_json(result)
            except Exception as exc:
                self._send_json({"status": "error", "message": str(exc)}, 500)
        elif path == "/api/queue/remove":
            _lazy_imports()
            job_id = data.get("job_id", "")
            if not job_id:
                self._send_json({"status": "error", "message": "缺少 job_id。"}, 400)
                return
            try:
                queue = _creators.load_job_queue(self._library_root())
                queue["jobs"] = [j for j in queue.get("jobs", []) if j.get("id") != job_id]
                _creators.write_job_queue(self._library_root(), queue)
                self._send_json({"status": "ok"})
            except Exception as exc:
                self._send_json({"status": "error", "message": str(exc)}, 500)
        elif path == "/api/queue/run":
            self._start_queue_job(data)
        else:
            self.send_error(404, "未找到 API")

    # ── Video Job ────────────────────────────────────────────────────

    def _start_video_job(self, data: dict[str, Any]) -> None:
        url = data.get("url", "").strip()
        if not url:
            self._send_json({"status": "error", "message": "缺少 url 字段。"}, 400)
            return

        settings = load_settings_with_default(self.library_root)
        library_root = self._library_root()
        cmd = [
            sys.executable, "-m", "clipvault", "video", url,
            "--library", str(library_root),
        ]
        if data.get("series"):
            cmd += ["--series", data["series"]]
        if data.get("force"):
            cmd.append("--force")
        device = data.get("device") or settings.get("device", "auto")
        model = data.get("model") or settings.get("model", "small")
        compute_type = data.get("compute_type") or settings.get("compute_type", "auto")
        simplify_chinese = _resolve_bool_option(data, settings, "simplify_chinese", True)
        cmd += ["--device", device, "--model", model, "--compute-type", compute_type]
        if not simplify_chinese:
            cmd.append("--no-simplify-chinese")
        if settings.get("cookies"):
            cmd += ["--cookies", settings["cookies"]]
        if data.get("keep_audio"):
            cmd.append("--keep-audio")

        job = Job(secrets.token_hex(8), "video", cmd, log_root=library_root / "_job_logs")
        if not _JOB_MANAGER.start(job):
            self._send_json({"status": "error", "message": "当前已有任务在运行，请稍后再试。"}, 409)
            return

        self._send_json({"status": "ok", "job_id": job.job_id, "log_dir": str(job.log_dir) if job.log_dir else None})

    def _start_queue_job(self, data: dict[str, Any]) -> None:
        settings = load_settings_with_default(self.library_root)
        library_root = self._library_root()
        try:
            cmd = build_queue_run_command(library_root, settings, data)
        except ValueError as exc:
            self._send_json({"status": "error", "message": str(exc)}, 400)
            return

        job = Job(secrets.token_hex(8), "queue", cmd, log_root=library_root / "_job_logs")
        if not _JOB_MANAGER.start(job):
            self._send_json({"status": "error", "message": "当前已有任务在运行，请稍后再试。"}, 409)
            return

        self._send_json({"status": "ok", "job_id": job.job_id, "log_dir": str(job.log_dir) if job.log_dir else None})

    def _stop_job(self) -> None:
        job = _JOB_MANAGER.get_job()
        if job is None or job.status != "running":
            self._send_json({"status": "error", "message": "当前没有正在运行的任务。"}, 400)
            return
        if job.process is not None:
            job.process.terminate()
        self._send_json({"status": "ok", "message": "任务已终止。"})

    # ── SSE Event Stream ─────────────────────────────────────────────

    def _stream_events(self, params: dict[str, list[str]]) -> None:
        # SSE endpoint accepts token via query param (EventSource can't set headers)
        token = self.headers.get("X-ClipVault-Token", "")
        if not token:
            token = (params.get("token") or [""])[0]
        if token != self.server_token:
            self.send_error(401, "未授权：token 缺失或无效")
            return

        job_ids = params.get("job_id", [])
        if not job_ids:
            self.send_error(400, "缺少 job_id 参数")
            return
        target_id = job_ids[0]

        job = _JOB_MANAGER.get_job()
        if job is None or job.job_id != target_id:
            self.send_error(404, "未找到对应任务")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        last_sent = 0
        while job.status in ("queued", "running"):
            with job._cond:
                job._cond.wait(timeout=2.0)
            events = job.events[last_sent:]
            if events:
                for line in events:
                    self._sse_send("log", line)
                last_sent = len(job.events)

        # Send any remaining events
        remaining = job.events[last_sent:]
        for line in remaining:
            self._sse_send("log", line)

        if job.result is not None:
            self._sse_send("result", json.dumps(job.result))
        if job.error:
            self._sse_send("error", job.error)
        self._sse_send("done", json.dumps(_job_done_payload(job), ensure_ascii=False))

    def _sse_send(self, event: str, data: str) -> None:
        try:
            payload_lines = [f"event: {event}"]
            for line in str(data).splitlines() or [""]:
                payload_lines.append(f"data: {line}")
            payload = "\n".join(payload_lines) + "\n\n"
            self.wfile.write(payload.encode("utf-8"))
            self.wfile.flush()
        except BrokenPipeError:
            pass

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "*"))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-ClipVault-Token")
        self.end_headers()


def run_server(
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    library: Path | None = None,
) -> None:
    token = secrets.token_urlsafe(32)
    host = DEFAULT_HOST

    ClipVaultHandler.server_token = token
    ClipVaultHandler.library_root = library or (Path.cwd() / "library")

    server = http.server.ThreadingHTTPServer(
        (host, port),
        ClipVaultHandler,
    )

    url = f"http://{host}:{port}/?token={token}"
    emit_log("ui", f"本地界面服务启动：http://{host}:{port}", level="success")
    emit_log("ui", f"访问 token：{token}")

    if open_browser:
        emit_log("ui", "正在尝试打开浏览器…")
        webbrowser.open(url)
    else:
        emit_log("ui", f"请手动打开：{url}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(file=sys.stderr)
        emit_log("ui", "正在关闭本地界面服务")
        server.shutdown()
