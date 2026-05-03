from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .asr import transcribe_audio
from .exporters import write_outputs
from .library import build_manifest, first_text, video_directory, write_json
from .platforms import download_audio, extract_info
from .subtitles import get_platform_subtitles


DEFAULT_LIBRARY = Path.cwd() / "library"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="clipvault",
        description="Fetch Bilibili subtitles, or run ASR when subtitles are unavailable.",
    )
    parser.add_argument("url", help="Bilibili video URL, BV/AV URL, or b23.tv short link.")
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY, help="Subtitle library root.")
    parser.add_argument("--model", default="small", help="faster-whisper model size/name. Default: small.")
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="ASR device. Default: auto, which prefers CUDA when available.",
    )
    parser.add_argument("--compute-type", default="auto", help="faster-whisper compute type. Default: auto.")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if transcript.md exists.")
    parser.add_argument("--keep-audio", action="store_true", help="Keep downloaded audio after ASR.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show yt-dlp logs.")
    args = parser.parse_args(argv)

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
        )
    except Exception as exc:  # noqa: BLE001 - CLI should report cleanly
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(result, ensure_ascii=False, indent=2))


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
) -> dict[str, Any]:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not available in PATH.")

    info = extract_info(url, verbose=verbose)
    title = first_text(info, "title", default="untitled")
    uploader = first_text(info, "uploader", "channel", "creator", default="unknown-uploader")
    video_id = first_text(info, "id", "display_id", default="unknown-id")

    video_dir = video_directory(library, uploader=uploader, title=title, video_id=video_id)
    video_dir.mkdir(parents=True, exist_ok=True)

    md_path = video_dir / "transcript.md"
    if md_path.exists() and not force:
        return {
            "status": "cached",
            "title": title,
            "uploader": uploader,
            "video_id": video_id,
            "markdown": str(md_path),
            "folder": str(video_dir),
        }

    manifest = build_manifest(info, url=url, title=title, uploader=uploader, video_id=video_id)
    write_json(video_dir / "manifest.json", manifest)

    segments, source = get_platform_subtitles(info)
    if not segments:
        audio_path = download_audio(url, video_dir, verbose=verbose)
        segments = transcribe_audio(audio_path, model_name=model_name, device=device, compute_type=compute_type)
        source = "asr:faster-whisper"
        if not keep_audio:
            try:
                audio_path.unlink()
            except OSError:
                pass

    write_outputs(
        video_dir=video_dir,
        title=title,
        uploader=uploader,
        url=url,
        video_id=video_id,
        source=source,
        segments=segments,
    )

    return {
        "status": "ok",
        "source": source,
        "title": title,
        "uploader": uploader,
        "video_id": video_id,
        "segments": len(segments),
        "markdown": str(md_path),
        "folder": str(video_dir),
    }

