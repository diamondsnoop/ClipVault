from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .asr import TranscriptionResult, resolve_device, transcribe_audio
from .credentials import (
    PLATFORM_CREDENTIAL_KEYS,
    list_credentials,
    remove_credential,
    store_credential,
)
from .creators import (
    add_creator_source,
    enqueue_creator_videos,
    fetch_creator_videos,
    list_creator_sources,
    list_queue_jobs,
    load_job_queue,
    queue_status,
    write_job_queue,
)
from .exporters import write_outputs
from .library import (
    build_manifest,
    current_timestamp_iso,
    describe_subtitle_source,
    first_text,
    guess_platform,
    is_completed,
    rebuild_library_indexes,
    resolve_video_directory,
    update_library_indexes,
    update_manifest,
    video_directory,
    write_json,
)
from .auth import clear_cookie_cache
from .login import login_bilibili
from .postprocess import simplify_chinese_segments
from .platforms import download_audio, extract_info
from .runtime_logs import emit_log
from .series_rules import resolve_series
from .subtitles import get_platform_subtitles


DEFAULT_LIBRARY = Path.cwd() / "library"
TOP_LEVEL_COMMANDS = {"video", "library", "creator", "queue", "auth", "ui"}
CLIPVAULT_AUTH_SENTINEL = "__clipvault_auth__"


def main(argv: list[str] | None = None) -> None:
    raw_args = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(_normalize_legacy_args(raw_args))

    try:
        result = run_parsed_args(args)
    except Exception as exc:  # noqa: BLE001 - CLI should report cleanly
        emit_log("pipeline", str(exc), level="error")
        raise SystemExit(1) from exc
    finally:
        clear_cookie_cache()

    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipvault",
        description="本地优先的视频字幕仓库。",
    )
    _add_library_option(parser)
    _add_cookies_option(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_video_parser(subparsers)
    _add_library_parser(subparsers)
    _add_creator_parser(subparsers)
    _add_queue_parser(subparsers)
    _add_auth_parser(subparsers)
    _add_ui_parser(subparsers)
    return parser


def _add_library_option(parser: argparse.ArgumentParser, *, default: Any = DEFAULT_LIBRARY) -> None:
    parser.add_argument("--library", type=Path, default=default, help="字幕仓库根目录。")


def _add_cookies_option(parser: argparse.ArgumentParser, *, default: Any = None) -> None:
    parser.add_argument(
        "--cookies",
        nargs="?",
        const=CLIPVAULT_AUTH_SENTINEL,
        default=default,
        help="Netscape cookies 文件路径；若不带值则使用已保存凭据（`--cookies`）。",
    )


def _add_video_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "video",
        help="处理单个视频 URL。",
        description="优先获取平台字幕；没有可用字幕时回退到本地 ASR。",
    )
    parser.add_argument("url", help="视频 URL（Bilibili、YouTube 等）。")
    _add_library_option(parser, default=argparse.SUPPRESS)
    _add_cookies_option(parser, default=argparse.SUPPRESS)
    parser.add_argument("--model", default="small", help="faster-whisper 模型名称。默认：small。")
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="ASR 设备。默认：auto；检测到可用 CUDA 时优先使用。",
    )
    parser.add_argument("--compute-type", default="auto", help="faster-whisper 计算类型。默认：auto。")
    parser.add_argument(
        "--simplify-chinese",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="将 ASR 中文输出从繁体转换为简体。默认开启。",
    )
    parser.add_argument("--force", action="store_true", help="即使已有完整字幕缓存也重新处理。")
    parser.add_argument("--keep-audio", action="store_true", help="ASR 后保留下载的音频文件。")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示 yt-dlp 详细日志。")
    parser.add_argument(
        "--series",
        type=str,
        default=None,
        help="可选系列名，用于仓库归档分组。",
    )
    parser.set_defaults(handler=_run_video_command)


def _add_library_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("library", help="维护本地字幕仓库。")
    library_subparsers = parser.add_subparsers(dest="library_command", required=True)
    rebuild_parser = library_subparsers.add_parser(
        "rebuild-index",
        help="根据现有 manifest 重建创作者和系列索引。",
    )
    _add_library_option(rebuild_parser, default=argparse.SUPPRESS)
    rebuild_parser.add_argument("--dry-run", action="store_true", help="只报告计划变更，不实际写入索引。")
    rebuild_parser.set_defaults(handler=_run_library_rebuild_index)


def _add_creator_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("creator", help="管理已登记的创作者来源。")
    creator_subparsers = parser.add_subparsers(dest="creator_command", required=True)
    add_parser = creator_subparsers.add_parser("add", help="记录一个创作者/频道来源 URL。")
    add_parser.add_argument("url", help="要追踪的创作者/频道 URL。")
    _add_library_option(add_parser, default=argparse.SUPPRESS)
    add_parser.add_argument("--name", type=str, default=None, help="该创作者的显示名称。")
    add_parser.set_defaults(handler=_run_creator_add)

    list_parser = creator_subparsers.add_parser("list", help="列出已记录的创作者来源。")
    _add_library_option(list_parser, default=argparse.SUPPRESS)
    list_parser.set_defaults(handler=_run_creator_list)

    fetch_parser = creator_subparsers.add_parser("fetch", help="抓取指定创作者的最近视频条目预览。")
    fetch_parser.add_argument("selector", help="创作者 id、名称或来源 URL。")
    _add_library_option(fetch_parser, default=argparse.SUPPRESS)
    _add_cookies_option(fetch_parser, default=argparse.SUPPRESS)
    fetch_parser.add_argument("--limit", type=int, default=20, help="最多抓取多少条。默认：20。")
    fetch_parser.add_argument("--verbose", "-v", action="store_true", help="显示 yt-dlp 详细日志。")
    fetch_parser.set_defaults(handler=_run_creator_fetch)

    enqueue_parser = creator_subparsers.add_parser("enqueue", help="将新视频加入本地字幕任务队列。")
    enqueue_parser.add_argument("selector", help="创作者 id、名称或来源 URL。")
    _add_library_option(enqueue_parser, default=argparse.SUPPRESS)
    _add_cookies_option(enqueue_parser, default=argparse.SUPPRESS)
    enqueue_parser.add_argument("--limit", type=int, default=20, help="最多检查多少条。默认：20。")
    enqueue_parser.add_argument("--verbose", "-v", action="store_true", help="显示 yt-dlp 详细日志。")
    enqueue_parser.set_defaults(handler=_run_creator_enqueue)


def _add_queue_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("queue", help="查看并执行字幕任务队列。")
    queue_subparsers = parser.add_subparsers(dest="queue_command", required=True)

    list_parser = queue_subparsers.add_parser("list", help="列出队列中的字幕任务。")
    _add_library_option(list_parser, default=argparse.SUPPRESS)
    list_parser.add_argument("--status", type=str, default=None, help="按任务状态过滤。")
    list_parser.set_defaults(handler=_run_queue_list)

    status_parser = queue_subparsers.add_parser("status", help="汇总队列任务状态。")
    _add_library_option(status_parser, default=argparse.SUPPRESS)
    status_parser.set_defaults(handler=_run_queue_status)

    run_parser = queue_subparsers.add_parser("run", help="执行待处理的字幕任务。")
    _add_library_option(run_parser, default=argparse.SUPPRESS)
    _add_cookies_option(run_parser, default=argparse.SUPPRESS)
    run_parser.add_argument("--limit", type=int, default=1, help="最多执行多少个任务。默认：1。")
    run_parser.add_argument("--retry-failed", action="store_true", help="同时重试失败任务。")
    run_parser.add_argument("--model", default="small", help="faster-whisper 模型名称。默认：small。")
    run_parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="ASR 设备。默认：auto；检测到可用 CUDA 时优先使用。",
    )
    run_parser.add_argument("--compute-type", default="auto", help="faster-whisper 计算类型。默认：auto。")
    run_parser.add_argument(
        "--simplify-chinese",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="将 ASR 中文输出从繁体转换为简体。默认开启。",
    )
    run_parser.add_argument("--keep-audio", action="store_true", help="ASR 后保留下载的音频文件。")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="显示 yt-dlp 详细日志。")
    run_parser.set_defaults(handler=_run_queue_run)


def _normalize_legacy_args(args: list[str]) -> list[str]:
    args = _normalize_cookies_optional_values(args)
    if not args or args[0] in TOP_LEVEL_COMMANDS:
        return args
    if args[0] in {"-h", "--help"}:
        return args
    command_index = _top_level_command_index_after_leading_globals(args)
    if command_index is not None:
        return args
    insert_at = _leading_global_options_end(args)
    return [*args[:insert_at], "video", *args[insert_at:]]


def _normalize_cookies_optional_values(args: list[str]) -> list[str]:
    normalized: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token != "--cookies":
            normalized.append(token)
            index += 1
            continue

        next_token = args[index + 1] if index + 1 < len(args) else None
        if (
            next_token is None
            or next_token.startswith("-")
            or next_token in TOP_LEVEL_COMMANDS
            or _looks_like_video_url(next_token)
        ):
            normalized.append(f"--cookies={CLIPVAULT_AUTH_SENTINEL}")
            index += 1
            continue

        normalized.extend([token, next_token])
        index += 2
    return normalized


def _looks_like_video_url(value: str) -> bool:
    lower = value.lower()
    return "://" in lower or lower.startswith(("www.", "bilibili.com/", "youtube.com/", "youtu.be/", "b23.tv/"))


def _top_level_command_index_after_leading_globals(args: list[str]) -> int | None:
    index = 0
    while index < len(args):
        token = args[index]
        if token in TOP_LEVEL_COMMANDS:
            return index
        next_index = _consume_leading_global_option(args, index)
        if next_index == index:
            return None
        index = next_index
    return None


def _leading_global_options_end(args: list[str]) -> int:
    index = 0
    while index < len(args):
        next_index = _consume_leading_global_option(args, index)
        if next_index == index:
            return index
        index = next_index
    return index


def _consume_leading_global_option(args: list[str], index: int) -> int:
    token = args[index]
    if token in {"--library", "--cookies"}:
        return index + 2 if index + 1 < len(args) else index
    if token.startswith("--library=") or token.startswith("--cookies="):
        return index + 1
    return index


def run_parsed_args(args: argparse.Namespace) -> dict[str, Any]:
    return args.handler(args)


def process_library_command(argv: list[str] | None = None) -> dict[str, Any]:
    args = build_parser().parse_args(["library", *(argv or [])])
    return run_parsed_args(args)


def process_creator_command(argv: list[str] | None = None) -> dict[str, Any]:
    args = build_parser().parse_args(["creator", *(argv or [])])
    return run_parsed_args(args)


def process_queue_command(argv: list[str] | None = None) -> dict[str, Any]:
    args = build_parser().parse_args(["queue", *(argv or [])])
    return run_parsed_args(args)


def _add_auth_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "auth",
        help="管理平台凭据。",
    )
    auth_subparsers = parser.add_subparsers(dest="auth_command", required=True)

    login = auth_subparsers.add_parser(
        "login",
        help="登录平台（二维码或手动 Cookie）。",
    )
    login.add_argument(
        "--platform", "-p",
        nargs="?",
        default="bilibili",
        choices=tuple(PLATFORM_CREDENTIAL_KEYS),
        help="目标平台。默认：bilibili（二维码登录）。",
    )
    login.add_argument("--mode", choices=("terminal", "web"), default="terminal",
                       help="二维码显示方式（终端字符块或浏览器）。默认：terminal。")
    login.add_argument("--sessdata", type=str, default=None, help="Bilibili 的 SESSDATA Cookie。")
    login.add_argument("--bili-jct", type=str, default=None, help="Bilibili 的 bili_jct Cookie。")
    login.add_argument("--session", type=str, default=None, help="Douyin 的 session Cookie。")
    login.set_defaults(handler=_run_auth_login)

    auth_subparsers.add_parser("list", help="按平台显示已保存的凭据字段。").set_defaults(
        handler=_run_auth_list
    )

    logout = auth_subparsers.add_parser("logout", help="移除某个平台的已保存凭据。")
    logout.add_argument(
        "--platform", "-p",
        required=True,
        choices=tuple(PLATFORM_CREDENTIAL_KEYS),
        help="要移除凭据的平台。",
    )
    logout.set_defaults(handler=_run_auth_logout)


def _add_ui_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("ui", help="启动本地 Web UI。")
    parser.add_argument("--port", type=int, default=8080, help="服务端口。默认：8080。")
    parser.add_argument("--no-open", action="store_true", default=False, help="启动后不自动打开浏览器。")
    _add_library_option(parser, default=argparse.SUPPRESS)
    parser.set_defaults(handler=_run_ui)


def _run_ui(args: argparse.Namespace) -> dict[str, Any]:
    from .ui.server import run_server

    library = getattr(args, "library", None) or DEFAULT_LIBRARY
    run_server(port=args.port, open_browser=not args.no_open, library=library)
    return {"status": "ok", "message": "本地界面服务已停止。"}


def _run_auth_login(args: argparse.Namespace) -> dict[str, Any]:
    # Check if any manual cookie values were provided
    manual_keys = [k for k in PLATFORM_CREDENTIAL_KEYS[args.platform] if getattr(args, k, None)]

    if manual_keys:
        # Manual mode: store provided credentials directly
        creds: dict[str, str] = {}
        for key in manual_keys:
            val = getattr(args, key, None)
            if val:
                creds[key] = val
        path = store_credential(args.platform, **creds)
        return {"status": "ok", "platform": args.platform, "keys": list(creds), "path": str(path)}

    # Auto mode: QR code login (only supported for bilibili)
    if args.platform == "bilibili":
        return login_bilibili(mode=args.mode)

    # For other platforms without QR support, show usage
    known_keys = PLATFORM_CREDENTIAL_KEYS[args.platform]
    return {
        "status": "error",
        "message": f"未提供凭据值，且平台 “{args.platform}” 还不支持二维码登录。"
                   f"可用命令：clipvault auth login --platform {args.platform} "
                   f"{' '.join(f'--{k}' for k in known_keys)}",
    }


def _run_auth_list(args: argparse.Namespace) -> dict[str, Any]:
    return {"status": "ok", "credentials": list_credentials()}


def _run_auth_logout(args: argparse.Namespace) -> dict[str, Any]:
    removed = remove_credential(args.platform)
    if not removed:
        return {"status": "error", "message": f"未找到平台 “{args.platform}” 的已保存凭据。"}
    clear_cookie_cache()
    return {"status": "ok", "platform": args.platform}


def _run_video_command(args: argparse.Namespace) -> dict[str, Any]:
    return process_video(
        url=args.url,
        library=args.library,
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type,
        simplify_chinese=args.simplify_chinese,
        force=args.force,
        keep_audio=args.keep_audio,
        verbose=args.verbose,
        series=args.series,
        cookies=args.cookies,
    )


def _run_library_rebuild_index(args: argparse.Namespace) -> dict[str, Any]:
    return rebuild_library_indexes(args.library, dry_run=args.dry_run)


def _run_creator_add(args: argparse.Namespace) -> dict[str, Any]:
    record = add_creator_source(args.library, source_url=args.url, name=args.name)
    return {"status": "ok", "creator": record}


def _run_creator_list(args: argparse.Namespace) -> dict[str, Any]:
    return {"status": "ok", "creators": list_creator_sources(args.library)}


def _run_creator_fetch(args: argparse.Namespace) -> dict[str, Any]:
    return fetch_creator_videos(
        args.library,
        selector=args.selector,
        limit=args.limit,
        verbose=args.verbose,
        cookies=args.cookies,
    )


def _run_creator_enqueue(args: argparse.Namespace) -> dict[str, Any]:
    return enqueue_creator_videos(
        args.library,
        selector=args.selector,
        limit=args.limit,
        verbose=args.verbose,
        cookies=args.cookies,
    )


def _run_queue_list(args: argparse.Namespace) -> dict[str, Any]:
    return {"status": "ok", "jobs": list_queue_jobs(args.library, status=args.status)}


def _run_queue_status(args: argparse.Namespace) -> dict[str, Any]:
    return queue_status(args.library)


def _run_queue_run(args: argparse.Namespace) -> dict[str, Any]:
    if args.limit < 1:
        raise ValueError("limit 至少为 1")

    queue = load_job_queue(args.library)
    eligible = {"pending", "failed"} if args.retry_failed else {"pending"}
    jobs = [job for job in queue.get("jobs", []) if job.get("status") in eligible][: args.limit]
    emit_log("queue", f"准备执行 {len(jobs)} 个任务")

    succeeded = 0
    failed = 0
    results: list[dict[str, Any]] = []
    for job in jobs:
        source_url = str(job.get("source_url") or "").strip()
        if not source_url:
            job["status"] = "failed"
            job["last_error"] = "缺少 source_url"
            failed += 1
            continue
        emit_log("queue", f"开始执行任务：{job.get('id')} {source_url}")
        job["status"] = "running"
        job["last_error"] = None
        write_job_queue(args.library, queue)
        try:
            result = process_video(
                url=source_url,
                library=args.library,
                model_name=args.model,
                device=args.device,
                compute_type=args.compute_type,
                simplify_chinese=args.simplify_chinese,
                force=False,
                keep_audio=args.keep_audio,
                verbose=args.verbose,
                series=None,
                cookies=args.cookies,
            )
        except Exception as exc:  # noqa: BLE001 - per-job failure should be recorded
            job["status"] = "failed"
            job["last_error"] = str(exc)
            failed += 1
            emit_log("queue", f"任务失败：{job.get('id')}（{exc}）", level="error")
        else:
            job["status"] = "done"
            job["result"] = {
                "folder": result.get("folder"),
                "markdown": result.get("markdown"),
                "source": result.get("source"),
            }
            succeeded += 1
            results.append({"job_id": job.get("id"), "result": result})
            emit_log("queue", f"任务完成：{job.get('id')}", level="success")
        finally:
            write_job_queue(args.library, queue)

    return {
        "status": "ok",
        "processed_count": len(jobs),
        "succeeded_count": succeeded,
        "failed_count": failed,
        "results": results,
    }


def _count_srt_segments(srt_path: Path) -> int:
    """Count subtitle blocks in an SRT file. Returns 0 if the file is missing."""
    try:
        content = srt_path.read_text(encoding="utf-8").strip()
        if not content:
            return 0
        return len([b for b in content.split("\n\n") if b.strip()])
    except (FileNotFoundError, OSError):
        return 0


def process_video(
    *,
    url: str,
    library: Path,
    model_name: str,
    device: str,
    compute_type: str,
    force: bool,
    keep_audio: bool,
    verbose: bool,
    series: str | None = None,
    cookies: Path | str | None = None,
    simplify_chinese: bool = True,
) -> dict[str, Any]:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("系统 PATH 中未找到 ffmpeg，请先安装并确保命令可用。")

    emit_log("pipeline", f"开始处理：{url}")
    info = extract_info(url, verbose=verbose, cookies=cookies)
    title = first_text(info, "title", default="untitled")
    uploader = first_text(info, "uploader", "channel", "creator", default="unknown-uploader")
    video_id = first_text(info, "id", "display_id", default="unknown-id")
    platform = guess_platform(url)
    emit_log("platform", f"已识别平台：{platform}")

    # Resolve series: explicit --series takes priority, otherwise auto-rules
    series, series_source = resolve_series(
        library, platform=platform, uploader=uploader, title=title, explicit_series=series,
    )
    if series:
        emit_log("library", f"系列归档：{series}")

    # Check cache (handles both new platform-aware and legacy paths)
    video_dir = resolve_video_directory(
        library, platform=platform, uploader=uploader, title=title, video_id=video_id, series=series,
    )
    if is_completed(video_dir) and not force:
        md_path = video_dir / "transcript.md"
        emit_log("cache", f"命中缓存：{video_dir}", level="success")
        # Update indexes so pre-index caches get indexed
        cached_manifest: dict[str, Any] = {}
        try:
            cached_manifest = json.loads((video_dir / "manifest.json").read_text(encoding="utf-8"))
            update_library_indexes(video_dir, cached_manifest, library)
        except Exception as exc:
            emit_log("index", f"缓存命中后的索引更新失败：{video_dir}（{exc}）", level="warning")
        source = cached_manifest.get("subtitle_source")
        source_label = cached_manifest.get("subtitle_source_label")
        source_detail = cached_manifest.get("subtitle_source_detail")
        if not source_label and source:
            source_label, source_detail = describe_subtitle_source(str(source))
        segments = _count_srt_segments(video_dir / "transcript.srt")
        return {
            "status": "cached",
            "title": title,
            "uploader": uploader,
            "video_id": video_id,
            "platform": platform,
            "series": series,
            "series_source": series_source,
            "source": source,
            "source_label": source_label,
            "source_detail": source_detail,
            "segments": segments,
            "asr_model": cached_manifest.get("asr_model"),
            "asr_device": cached_manifest.get("asr_device"),
            "markdown": str(md_path) if md_path.exists() else None,
            "folder": str(video_dir),
        }

    # New processing always uses platform-aware path
    video_dir = video_directory(library, platform=platform, uploader=uploader, title=title, video_id=video_id, series=series)
    video_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(info, url=url, title=title, uploader=uploader, video_id=video_id, series=series)
    manifest_path = video_dir / "manifest.json"
    write_json(manifest_path, manifest)

    source = ""
    actual_asr_device: str | None = None
    segments: list[Any] = []
    try:
        segments, source = get_platform_subtitles(info, platform=platform, cookies=cookies)
        if not segments:
            emit_log("subtitle", "未找到可用平台字幕，回退到本地 ASR", level="warning")
            audio_path = download_audio(url, video_dir, verbose=verbose, cookies=cookies)
            transcription = transcribe_audio(audio_path, model_name=model_name, device=device, compute_type=compute_type)
            if isinstance(transcription, TranscriptionResult):
                segments = transcription.segments
                actual_asr_device = transcription.device
            else:
                segments = transcription
                actual_asr_device = resolve_device(device)
            source = "asr:faster-whisper"
            if simplify_chinese:
                try:
                    segments = simplify_chinese_segments(segments)
                except RuntimeError as exc:
                    emit_log("asr", f"{exc} 已跳过中文转简。", level="warning")
                else:
                    emit_log("asr", "已将中文 ASR 结果转换为简体中文", level="success")
            if not keep_audio:
                try:
                    audio_path.unlink()
                except OSError:
                    pass
        else:
            emit_log("subtitle", f"将使用平台字幕：{source}", level="success")

        write_outputs(
            video_dir=video_dir,
            title=title,
            uploader=uploader,
            url=url,
            video_id=video_id,
            source=source,
            segments=segments,
        )

        emit_log("export", f"已写出 SRT：{video_dir / 'transcript.srt'}", level="success")
        emit_log("export", f"已写出 TXT：{video_dir / 'transcript.txt'}", level="success")
        emit_log("export", f"已写出 Markdown：{video_dir / 'transcript.md'}", level="success")

        source_label, source_detail = describe_subtitle_source(source)
        manifest_updates: dict[str, Any] = {
            "processed_at": current_timestamp_iso(),
            "processing_state": "completed",
            "failed_at": None,
            "last_error": None,
            "subtitle_source": source,
            "subtitle_source_label": source_label,
            "subtitle_source_detail": source_detail,
            "output_files": ["transcript.srt", "transcript.txt", "transcript.md"],
        }
        if source.startswith("asr:"):
            manifest_updates["asr_model"] = model_name
            manifest_updates["asr_device"] = actual_asr_device
        final_manifest: dict[str, Any] | None = None
        try:
            final_manifest = update_manifest(manifest_path, fallback=manifest, **manifest_updates)
        except RuntimeError as exc:
            emit_log("library", f"更新 manifest 失败：{exc}", level="error")

        # Update indexes after manifest is final
        if final_manifest is not None:
            try:
                update_library_indexes(video_dir, final_manifest, library)
            except Exception as exc:
                emit_log("index", f"处理完成后的索引更新失败：{video_dir}（{exc}）", level="warning")

        return {
            "status": "ok",
            "source": source,
            "source_label": source_label,
            "source_detail": source_detail,
            "title": title,
            "uploader": uploader,
            "video_id": video_id,
            "platform": platform,
            "series": series,
            "series_source": series_source,
            "segments": len(segments),
            "asr_model": manifest_updates.get("asr_model"),
            "asr_device": manifest_updates.get("asr_device"),
            "markdown": str(video_dir / "transcript.md"),
            "folder": str(video_dir),
        }
    except Exception as exc:
        failure_updates: dict[str, Any] = {
            "processed_at": current_timestamp_iso(),
            "processing_state": "failed",
            "failed_at": current_timestamp_iso(),
            "last_error": str(exc),
            "output_files": [],
        }
        if source:
            source_label, source_detail = describe_subtitle_source(source)
            failure_updates["subtitle_source"] = source
            failure_updates["subtitle_source_label"] = source_label
            failure_updates["subtitle_source_detail"] = source_detail
        if source.startswith("asr:"):
            failure_updates["asr_model"] = model_name
            failure_updates["asr_device"] = actual_asr_device
        try:
            update_manifest(manifest_path, fallback=manifest, **failure_updates)
        except RuntimeError as manifest_exc:
            emit_log("library", f"写入失败状态 manifest 失败：{manifest_exc}", level="warning")
        raise
