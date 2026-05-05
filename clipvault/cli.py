from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .asr import resolve_device, transcribe_audio
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
from .login import login_bilibili
from .platforms import download_audio, extract_info
from .series_rules import resolve_series
from .subtitles import get_platform_subtitles


DEFAULT_LIBRARY = Path.cwd() / "library"
TOP_LEVEL_COMMANDS = {"video", "library", "creator", "queue", "auth"}


def main(argv: list[str] | None = None) -> None:
    raw_args = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(_normalize_legacy_args(raw_args))

    try:
        result = run_parsed_args(args)
    except Exception as exc:  # noqa: BLE001 - CLI should report cleanly
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipvault",
        description="Local-first video transcript vault.",
    )
    _add_library_option(parser)
    _add_cookies_option(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_video_parser(subparsers)
    _add_library_parser(subparsers)
    _add_creator_parser(subparsers)
    _add_queue_parser(subparsers)
    _add_auth_parser(subparsers)
    return parser


def _add_library_option(parser: argparse.ArgumentParser, *, default: Any = DEFAULT_LIBRARY) -> None:
    parser.add_argument("--library", type=Path, default=default, help="Subtitle library root.")


def _add_cookies_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cookies",
        action="store_true",
        default=False,
        help="Use stored platform credentials for authenticated access.",
    )


def _add_video_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "video",
        help="Process one video URL.",
        description="Fetch video subtitles, or run ASR when subtitles are unavailable.",
    )
    parser.add_argument("url", help="Video URL (Bilibili, YouTube, etc.).")
    _add_library_option(parser, default=argparse.SUPPRESS)
    _add_cookies_option(parser)
    parser.add_argument("--model", default="small", help="faster-whisper model size/name. Default: small.")
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="ASR device. Default: auto, which prefers CUDA when available.",
    )
    parser.add_argument("--compute-type", default="auto", help="faster-whisper compute type. Default: auto.")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if transcript exists.")
    parser.add_argument("--keep-audio", action="store_true", help="Keep downloaded audio after ASR.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show yt-dlp logs.")
    parser.add_argument(
        "--series",
        type=str,
        default=None,
        help="Optional series name for library grouping.",
    )
    parser.set_defaults(handler=_run_video_command)


def _add_library_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("library", help="Maintain the local transcript library.")
    library_subparsers = parser.add_subparsers(dest="library_command", required=True)
    rebuild_parser = library_subparsers.add_parser(
        "rebuild-index",
        help="Rebuild creator and series indexes from existing manifests.",
    )
    _add_library_option(rebuild_parser, default=argparse.SUPPRESS)
    rebuild_parser.add_argument("--dry-run", action="store_true", help="Report planned changes without writing indexes.")
    rebuild_parser.set_defaults(handler=_run_library_rebuild_index)


def _add_creator_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("creator", help="Manage followed creator sources.")
    creator_subparsers = parser.add_subparsers(dest="creator_command", required=True)
    add_parser = creator_subparsers.add_parser("add", help="Record a creator/channel source URL.")
    add_parser.add_argument("url", help="Creator/channel URL to follow.")
    _add_library_option(add_parser, default=argparse.SUPPRESS)
    add_parser.add_argument("--name", type=str, default=None, help="Display name for this creator.")
    add_parser.set_defaults(handler=_run_creator_add)

    list_parser = creator_subparsers.add_parser("list", help="List recorded creator sources.")
    _add_library_option(list_parser, default=argparse.SUPPRESS)
    list_parser.set_defaults(handler=_run_creator_list)

    fetch_parser = creator_subparsers.add_parser("fetch", help="Fetch recent video entries for a recorded creator.")
    fetch_parser.add_argument("selector", help="Creator id, name, or source URL.")
    _add_library_option(fetch_parser, default=argparse.SUPPRESS)
    _add_cookies_option(fetch_parser)
    fetch_parser.add_argument("--limit", type=int, default=20, help="Maximum entries to fetch. Default: 20.")
    fetch_parser.add_argument("--verbose", "-v", action="store_true", help="Show yt-dlp logs.")
    fetch_parser.set_defaults(handler=_run_creator_fetch)

    enqueue_parser = creator_subparsers.add_parser("enqueue", help="Add new creator entries to the local transcript job queue.")
    enqueue_parser.add_argument("selector", help="Creator id, name, or source URL.")
    _add_library_option(enqueue_parser, default=argparse.SUPPRESS)
    _add_cookies_option(enqueue_parser)
    enqueue_parser.add_argument("--limit", type=int, default=20, help="Maximum entries to inspect. Default: 20.")
    enqueue_parser.add_argument("--verbose", "-v", action="store_true", help="Show yt-dlp logs.")
    enqueue_parser.set_defaults(handler=_run_creator_enqueue)


def _add_queue_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("queue", help="Inspect and run transcript jobs.")
    queue_subparsers = parser.add_subparsers(dest="queue_command", required=True)

    list_parser = queue_subparsers.add_parser("list", help="List queued transcript jobs.")
    _add_library_option(list_parser, default=argparse.SUPPRESS)
    list_parser.add_argument("--status", type=str, default=None, help="Filter by job status.")
    list_parser.set_defaults(handler=_run_queue_list)

    status_parser = queue_subparsers.add_parser("status", help="Summarize queued transcript jobs.")
    _add_library_option(status_parser, default=argparse.SUPPRESS)
    status_parser.set_defaults(handler=_run_queue_status)

    run_parser = queue_subparsers.add_parser("run", help="Run pending transcript jobs.")
    _add_library_option(run_parser, default=argparse.SUPPRESS)
    _add_cookies_option(run_parser)
    run_parser.add_argument("--limit", type=int, default=1, help="Maximum jobs to run. Default: 1.")
    run_parser.add_argument("--retry-failed", action="store_true", help="Run failed jobs as well as pending jobs.")
    run_parser.add_argument("--model", default="small", help="faster-whisper model size/name. Default: small.")
    run_parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="ASR device. Default: auto, which prefers CUDA when available.",
    )
    run_parser.add_argument("--compute-type", default="auto", help="faster-whisper compute type. Default: auto.")
    run_parser.add_argument("--keep-audio", action="store_true", help="Keep downloaded audio after ASR.")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Show yt-dlp logs.")
    run_parser.set_defaults(handler=_run_queue_run)


def _normalize_legacy_args(args: list[str]) -> list[str]:
    if not args or args[0] in TOP_LEVEL_COMMANDS:
        return args
    if args[0] in {"-h", "--help"}:
        return args
    if _leading_global_option_before_subcommand(args, "--library"):
        return args
    if args[0] == "--cookies":
        # --cookies is a flag (doesn't consume next arg), subcommand at args[1]
        if len(args) >= 2 and args[1] in TOP_LEVEL_COMMANDS:
            return args
        return ["video", *args]
    return ["video", *args]


def _leading_global_option_before_subcommand(args: list[str], option: str) -> bool:
    if args[0] == option and len(args) >= 3 and args[2] in TOP_LEVEL_COMMANDS:
        return True
    if args[0].startswith(f"{option}=") and len(args) >= 2 and args[1] in TOP_LEVEL_COMMANDS:
        return True
    return False


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
        help="Manage platform credentials.",
    )
    auth_subparsers = parser.add_subparsers(dest="auth_command", required=True)

    login = auth_subparsers.add_parser(
        "login",
        help="Log in to a platform (QR code or manual cookie entry).",
    )
    login.add_argument(
        "--platform", "-p",
        nargs="?",
        default="bilibili",
        choices=tuple(PLATFORM_CREDENTIAL_KEYS),
        help="Target platform. Default: bilibili (QR code login).",
    )
    login.add_argument("--mode", choices=("terminal", "web"), default="terminal",
                       help="QR code display mode (terminal blocks or browser). Default: terminal.")
    login.add_argument("--sessdata", type=str, default=None, help="Bilibili SESSDATA cookie.")
    login.add_argument("--bili-jct", type=str, default=None, help="Bilibili bili_jct cookie.")
    login.add_argument("--session", type=str, default=None, help="Douyin session cookie.")
    login.set_defaults(handler=_run_auth_login)

    auth_subparsers.add_parser("list", help="Show stored credential keys by platform.").set_defaults(
        handler=_run_auth_list
    )

    logout = auth_subparsers.add_parser("logout", help="Remove credentials for a platform.")
    logout.add_argument(
        "--platform", "-p",
        required=True,
        choices=tuple(PLATFORM_CREDENTIAL_KEYS),
        help="Platform to remove credentials for.",
    )
    logout.set_defaults(handler=_run_auth_logout)


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
        "message": f"No values provided and QR login is not yet supported for '{args.platform}'. "
                   f"Usage: clipvault auth login --platform {args.platform} "
                   f"{' '.join(f'--{k}' for k in known_keys)}",
    }


def _run_auth_list(args: argparse.Namespace) -> dict[str, Any]:
    return {"status": "ok", "credentials": list_credentials()}


def _run_auth_logout(args: argparse.Namespace) -> dict[str, Any]:
    removed = remove_credential(args.platform)
    if not removed:
        return {"status": "error", "message": f"No credentials found for platform '{args.platform}'."}
    return {"status": "ok", "platform": args.platform}


def _run_video_command(args: argparse.Namespace) -> dict[str, Any]:
    return process_video(
        url=args.url,
        library=args.library,
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type,
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
        raise ValueError("limit must be at least 1")

    queue = load_job_queue(args.library)
    eligible = {"pending", "failed"} if args.retry_failed else {"pending"}
    jobs = [job for job in queue.get("jobs", []) if job.get("status") in eligible][: args.limit]
    print(f"[queue] running: {len(jobs)}", file=sys.stderr)

    succeeded = 0
    failed = 0
    results: list[dict[str, Any]] = []
    for job in jobs:
        source_url = str(job.get("source_url") or "").strip()
        if not source_url:
            job["status"] = "failed"
            job["last_error"] = "missing source_url"
            failed += 1
            continue
        print(f"[queue] job start: {job.get('id')} {source_url}", file=sys.stderr)
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
            print(f"[queue] job failed: {job.get('id')} {exc}", file=sys.stderr)
        else:
            job["status"] = "done"
            job["result"] = {
                "folder": result.get("folder"),
                "markdown": result.get("markdown"),
                "source": result.get("source"),
            }
            succeeded += 1
            results.append({"job_id": job.get("id"), "result": result})
            print(f"[queue] job done: {job.get('id')}", file=sys.stderr)
        finally:
            write_job_queue(args.library, queue)

    return {
        "status": "ok",
        "processed_count": len(jobs),
        "succeeded_count": succeeded,
        "failed_count": failed,
        "results": results,
    }


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
) -> dict[str, Any]:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not available in PATH.")

    print(f"[pipeline] processing {url}", file=sys.stderr)
    info = extract_info(url, verbose=verbose, cookies=cookies)
    title = first_text(info, "title", default="untitled")
    uploader = first_text(info, "uploader", "channel", "creator", default="unknown-uploader")
    video_id = first_text(info, "id", "display_id", default="unknown-id")
    platform = guess_platform(url)
    print(f"[platform] {platform}", file=sys.stderr)

    # Resolve series: explicit --series takes priority, otherwise auto-rules
    series, series_source = resolve_series(
        library, platform=platform, uploader=uploader, title=title, explicit_series=series,
    )
    if series:
        print(f"[library] series: {series}", file=sys.stderr)

    # Check cache (handles both new platform-aware and legacy paths)
    video_dir = resolve_video_directory(
        library, platform=platform, uploader=uploader, title=title, video_id=video_id, series=series,
    )
    if is_completed(video_dir) and not force:
        md_path = video_dir / "transcript.md"
        print(f"[cache] hit: {video_dir}", file=sys.stderr)
        # Update indexes so pre-index caches get indexed
        try:
            cached_manifest = json.loads((video_dir / "manifest.json").read_text(encoding="utf-8"))
            update_library_indexes(video_dir, cached_manifest, library)
        except Exception as exc:
            print(f"[index] failed on cache hit ({video_dir}): {exc}", file=sys.stderr)
        return {
            "status": "cached",
            "title": title,
            "uploader": uploader,
            "video_id": video_id,
            "platform": platform,
            "series": series,
            "series_source": series_source,
            "markdown": str(md_path) if md_path.exists() else None,
            "folder": str(video_dir),
        }

    # New processing always uses platform-aware path
    video_dir = video_directory(library, platform=platform, uploader=uploader, title=title, video_id=video_id, series=series)
    video_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(info, url=url, title=title, uploader=uploader, video_id=video_id, series=series)
    write_json(video_dir / "manifest.json", manifest)

    segments, source = get_platform_subtitles(info, platform=platform, cookies=cookies)
    if not segments:
        print("[pipeline] no subtitles found, falling back to ASR", file=sys.stderr)
        audio_path = download_audio(url, video_dir, verbose=verbose, cookies=cookies)
        segments = transcribe_audio(audio_path, model_name=model_name, device=device, compute_type=compute_type)
        source = "asr:faster-whisper"
        if not keep_audio:
            try:
                audio_path.unlink()
            except OSError:
                pass
    else:
        print(f"[pipeline] using {source}", file=sys.stderr)

    write_outputs(
        video_dir=video_dir,
        title=title,
        uploader=uploader,
        url=url,
        video_id=video_id,
        source=source,
        segments=segments,
    )

    print(f"[export] srt: {video_dir / 'transcript.srt'}", file=sys.stderr)
    print(f"[export] txt: {video_dir / 'transcript.txt'}", file=sys.stderr)
    print(f"[export] md:  {video_dir / 'transcript.md'}", file=sys.stderr)

    manifest_updates: dict[str, Any] = {
        "subtitle_source": source,
        "output_files": ["transcript.srt", "transcript.txt", "transcript.md"],
    }
    if source.startswith("asr:"):
        manifest_updates["asr_model"] = model_name
        manifest_updates["asr_device"] = resolve_device(device)
    update_manifest(video_dir / "manifest.json", **manifest_updates)

    # Update indexes after manifest is final
    try:
        final_manifest = json.loads((video_dir / "manifest.json").read_text(encoding="utf-8"))
        update_library_indexes(video_dir, final_manifest, library)
    except Exception as exc:
        print(f"[index] failed ({video_dir}): {exc}", file=sys.stderr)

    return {
        "status": "ok",
        "source": source,
        "title": title,
        "uploader": uploader,
        "video_id": video_id,
        "platform": platform,
        "series": series,
        "series_source": series_source,
        "segments": len(segments),
        "markdown": str(video_dir / "transcript.md"),
        "folder": str(video_dir),
    }
