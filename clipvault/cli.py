from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .asr import resolve_device, transcribe_audio
from .creators import add_creator_source, list_creator_sources
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
from .platforms import download_audio, extract_info
from .series_rules import resolve_series
from .subtitles import get_platform_subtitles


DEFAULT_LIBRARY = Path.cwd() / "library"


def main(argv: list[str] | None = None) -> None:
    raw_args = sys.argv[1:] if argv is None else argv
    if raw_args and raw_args[0] == "library":
        result = process_library_command(raw_args[1:])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if raw_args and raw_args[0] == "creator":
        result = process_creator_command(raw_args[1:])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    parser = argparse.ArgumentParser(
        prog="clipvault",
        description="Fetch video subtitles, or run ASR when subtitles are unavailable.",
    )
    parser.add_argument("url", help="Video URL (Bilibili, YouTube, etc.).")
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY, help="Subtitle library root.")
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
    args = parser.parse_args(raw_args)

    try:
        result = process_video(
            url=args.url,
            library=args.library,
            model_name=args.model,
            device=args.device,
            compute_type=args.compute_type,
            force=args.force,
            keep_audio=args.keep_audio,
            verbose=args.verbose,
            series=args.series,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should report cleanly
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(result, ensure_ascii=False, indent=2))


def process_library_command(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        prog="clipvault library",
        description="Maintain the local ClipVault library.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    rebuild_parser = subparsers.add_parser(
        "rebuild-index",
        help="Rebuild creator and series indexes from existing manifests.",
    )
    rebuild_parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY, help="Subtitle library root.")
    rebuild_parser.add_argument("--dry-run", action="store_true", help="Report planned changes without writing indexes.")

    args = parser.parse_args(argv)
    if args.command == "rebuild-index":
        try:
            return rebuild_library_indexes(args.library, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001 - CLI should report cleanly
            print(f"[error] {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
    raise SystemExit(2)


def process_creator_command(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        prog="clipvault creator",
        description="Manage followed creator sources.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_parser = subparsers.add_parser("add", help="Record a creator/channel source URL.")
    add_parser.add_argument("url", help="Creator/channel URL to follow.")
    add_parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY, help="Subtitle library root.")
    add_parser.add_argument("--name", type=str, default=None, help="Display name for this creator.")

    list_parser = subparsers.add_parser("list", help="List recorded creator sources.")
    list_parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY, help="Subtitle library root.")

    args = parser.parse_args(argv)
    try:
        if args.command == "add":
            record = add_creator_source(args.library, source_url=args.url, name=args.name)
            return {"status": "ok", "creator": record}
        if args.command == "list":
            return {"status": "ok", "creators": list_creator_sources(args.library)}
    except Exception as exc:  # noqa: BLE001 - CLI should report cleanly
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(2)


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
) -> dict[str, Any]:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not available in PATH.")

    print(f"[pipeline] processing {url}", file=sys.stderr)
    info = extract_info(url, verbose=verbose)
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

    segments, source = get_platform_subtitles(info, platform=platform)
    if not segments:
        print("[pipeline] no subtitles found, falling back to ASR", file=sys.stderr)
        audio_path = download_audio(url, video_dir, verbose=verbose)
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
