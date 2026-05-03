from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_DLL_DIRECTORY_HANDLES: list[Any] = []


def add_nvidia_dll_directories() -> None:
    if os.name != "nt":
        return
    site_roots = [Path(path) for path in sys.path if "site-packages" in path]
    suffixes = (
        Path("nvidia") / "cublas" / "bin",
        Path("nvidia") / "cudnn" / "bin",
        Path("nvidia") / "cuda_nvrtc" / "bin",
        Path("nvidia") / "cuda_runtime" / "bin",
    )
    dll_dirs: list[str] = []
    for root in site_roots:
        for suffix in suffixes:
            dll_dir = root / suffix
            if dll_dir.exists():
                dll_dirs.append(str(dll_dir))
                _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(dll_dir)))
    if dll_dirs:
        os.environ["PATH"] = os.pathsep.join(dll_dirs + [os.environ.get("PATH", "")])


add_nvidia_dll_directories()

import ctranslate2  # noqa: E402
from faster_whisper import WhisperModel
from yt_dlp import YoutubeDL


DEFAULT_LIBRARY = Path.cwd() / "library"
LANG_PRIORITY = (
    "zh-CN",
    "zh-Hans",
    "zh-Hans-CN",
    "zh",
    "cmn-Hans-CN",
    "en",
)


@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="clipvault",
        description="Fetch Bilibili subtitles, or run ASR when subtitles are unavailable.",
    )
    parser.add_argument("url", help="Bilibili video URL, BV/AV URL, or b23.tv short link.")
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY, help="Subtitle library root.")
    parser.add_argument("--model", default="small", help="faster-whisper model size/name. Default: small.")
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto", help="ASR device. Default: auto, which prefers CUDA when available.")
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

    video_dir = library / safe_name(uploader) / safe_name(f"{title} - {video_id}")
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


def extract_info(url: str, *, verbose: bool) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": not verbose,
        "no_warnings": not verbose,
        "skip_download": True,
        "noplaylist": True,
        "proxy": "",
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not isinstance(info, dict):
        raise RuntimeError("yt-dlp did not return video metadata.")
    return info


def get_platform_subtitles(info: dict[str, Any]) -> tuple[list[SubtitleSegment], str]:
    tracks = []
    for source_name, field in (("subtitle", "subtitles"), ("automatic_caption", "automatic_captions")):
        subtitle_map = info.get(field) or {}
        if not isinstance(subtitle_map, dict):
            continue
        for lang, entries in subtitle_map.items():
            priority = language_priority(lang)
            if priority is None:
                continue
            for entry in entries or []:
                if isinstance(entry, dict) and entry.get("url"):
                    tracks.append((priority, source_name, lang, entry))

    tracks.sort(key=lambda item: (item[0], preferred_ext_rank(item[3].get("ext"))))
    for _, source_name, lang, entry in tracks:
        try:
            raw = fetch_text(entry["url"])
            segments = parse_subtitle(raw, entry.get("ext") or "")
            if segments:
                return segments, f"{source_name}:{lang}:{entry.get('ext') or 'unknown'}"
        except Exception:
            continue
    return [], "none"


def language_priority(lang: str) -> int | None:
    normalized = lang.strip()
    for index, candidate in enumerate(LANG_PRIORITY):
        if normalized == candidate or normalized.lower().startswith(candidate.lower()):
            return index
    if normalized.lower().startswith("zh"):
        return 10
    return None


def preferred_ext_rank(ext: str | None) -> int:
    return {"json": 0, "json3": 1, "vtt": 2, "srt": 3}.get((ext or "").lower(), 9)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=30) as response:  # noqa: S310 - user supplied video subtitle URL
        return response.read().decode("utf-8", errors="replace")


def parse_subtitle(raw: str, ext: str) -> list[SubtitleSegment]:
    text = raw.lstrip("\ufeff").strip()
    if not text:
        return []
    if ext.lower() in {"json", "json3"} or text.startswith("{"):
        return parse_json_subtitle(text)
    if "WEBVTT" in text[:64]:
        return parse_vtt(text)
    return parse_srt(text)


def parse_json_subtitle(raw: str) -> list[SubtitleSegment]:
    data = json.loads(raw)
    body = data.get("body") or data.get("events") or []
    segments: list[SubtitleSegment] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        if "content" in item:
            start = float(item.get("from", 0))
            end = float(item.get("to", start))
            text = clean_text(str(item.get("content", "")))
        else:
            start = float(item.get("tStartMs", 0)) / 1000
            duration = float(item.get("dDurationMs", 0)) / 1000
            end = start + duration
            segs = item.get("segs") or []
            text = clean_text("".join(str(seg.get("utf8", "")) for seg in segs if isinstance(seg, dict)))
        if text:
            segments.append(SubtitleSegment(start=start, end=max(end, start), text=text))
    return segments


def parse_vtt(raw: str) -> list[SubtitleSegment]:
    segments: list[SubtitleSegment] = []
    lines = [line.strip("\ufeff") for line in raw.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue
        start_s, end_s = split_time_range(line)
        i += 1
        content: list[str] = []
        while i < len(lines) and lines[i].strip():
            content.append(strip_tags(lines[i].strip()))
            i += 1
        text = clean_text(" ".join(content))
        if text:
            segments.append(SubtitleSegment(parse_time(start_s), parse_time(end_s), text))
    return segments


def parse_srt(raw: str) -> list[SubtitleSegment]:
    segments: list[SubtitleSegment] = []
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n"))
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        time_line = next((line for line in lines if "-->" in line), "")
        if not time_line:
            continue
        idx = lines.index(time_line)
        start_s, end_s = split_time_range(time_line)
        text = clean_text(" ".join(strip_tags(line) for line in lines[idx + 1 :]))
        if text:
            segments.append(SubtitleSegment(parse_time(start_s), parse_time(end_s), text))
    return segments


def split_time_range(line: str) -> tuple[str, str]:
    left, right = line.split("-->", 1)
    return left.strip(), right.strip().split()[0]


def parse_time(value: str) -> float:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = "0", parts[0], parts[1]
    else:
        return float(value)
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def download_audio(url: str, video_dir: Path, *, verbose: bool) -> Path:
    output = str(video_dir / "source_audio.%(ext)s")
    opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": output,
        "quiet": not verbose,
        "no_warnings": not verbose,
        "noplaylist": True,
        "proxy": "",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }
        ],
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    matches = sorted(video_dir.glob("source_audio.*"))
    if not matches:
        raise RuntimeError("Audio download finished, but no source_audio file was found.")
    return matches[0]


def transcribe_audio(audio_path: Path, *, model_name: str, device: str, compute_type: str) -> list[SubtitleSegment]:
    resolved_model = resolve_local_model(model_name)
    resolved_device = resolve_device(device)
    resolved_compute_type = resolve_compute_type(compute_type, resolved_device)
    return transcribe_audio_once(
        audio_path,
        resolved_model=resolved_model,
        device=resolved_device,
        compute_type=resolved_compute_type,
        allow_cpu_fallback=(device == "auto"),
    )


def transcribe_audio_once(
    audio_path: Path,
    *,
    resolved_model: str,
    device: str,
    compute_type: str,
    allow_cpu_fallback: bool,
) -> list[SubtitleSegment]:
    print(f"[asr] model={resolved_model} device={device} compute_type={compute_type}", file=sys.stderr)
    try:
        model = WhisperModel(
            resolved_model,
            device=device,
            compute_type=compute_type,
            local_files_only=True,
        )
    except RuntimeError as exc:
        if device == "cuda" and allow_cpu_fallback:
            print(f"[asr] CUDA unavailable ({exc}); falling back to CPU.", file=sys.stderr)
            return transcribe_audio_once(
                audio_path,
                resolved_model=resolved_model,
                device="cpu",
                compute_type="int8",
                allow_cpu_fallback=False,
            )
        raise
    segments_iter, _info = model.transcribe(
        str(audio_path),
        language="zh",
        vad_filter=True,
        beam_size=5,
    )
    segments: list[SubtitleSegment] = []
    try:
        for segment in segments_iter:
            text = clean_text(segment.text)
            if text:
                segments.append(SubtitleSegment(float(segment.start), float(segment.end), text))
    except RuntimeError as exc:
        if device == "cuda" and allow_cpu_fallback:
            print(f"[asr] CUDA transcription failed ({exc}); falling back to CPU.", file=sys.stderr)
            return transcribe_audio_once(
                audio_path,
                resolved_model=resolved_model,
                device="cpu",
                compute_type="int8",
                allow_cpu_fallback=False,
            )
        raise
    if not segments:
        raise RuntimeError("ASR completed but returned no text.")
    return segments


def resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def resolve_compute_type(compute_type: str, device: str) -> str:
    if compute_type != "auto":
        return compute_type
    if device == "cuda":
        return "int8_float16"
    return "int8"


def resolve_local_model(model_name: str) -> str:
    model_name = model_name.strip()
    if Path(model_name).exists():
        return model_name
    if "/" in model_name:
        return model_name

    cache_root = Path.home() / ".cache" / "huggingface" / "hub" / f"models--Systran--faster-whisper-{model_name}" / "snapshots"
    if cache_root.exists():
        snapshots = sorted((path for path in cache_root.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime, reverse=True)
        if snapshots:
            return str(snapshots[0])
    return f"Systran/faster-whisper-{model_name}"


def write_outputs(
    *,
    video_dir: Path,
    title: str,
    uploader: str,
    url: str,
    video_id: str,
    source: str,
    segments: list[SubtitleSegment],
) -> None:
    (video_dir / "transcript.srt").write_text(to_srt(segments), encoding="utf-8")
    (video_dir / "transcript.txt").write_text(to_plain_text(segments), encoding="utf-8")
    (video_dir / "transcript.md").write_text(
        to_markdown(title=title, uploader=uploader, url=url, video_id=video_id, source=source, segments=segments),
        encoding="utf-8",
    )


def to_srt(segments: list[SubtitleSegment]) -> str:
    blocks = []
    for index, seg in enumerate(segments, start=1):
        blocks.append(f"{index}\n{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}\n{seg.text}")
    return "\n\n".join(blocks) + "\n"


def to_plain_text(segments: list[SubtitleSegment]) -> str:
    return "\n".join(f"[{format_clock(seg.start)}] {seg.text}" for seg in segments) + "\n"


def to_markdown(
    *,
    title: str,
    uploader: str,
    url: str,
    video_id: str,
    source: str,
    segments: list[SubtitleSegment],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 来源：{url}",
        f"- UP主：{uploader}",
        f"- 视频ID：{video_id}",
        f"- 字幕来源：{source}",
        "",
        "## 字幕正文",
        "",
    ]
    lines.extend(f"- `{format_clock(seg.start)}` {seg.text}" for seg in segments)
    lines.append("")
    return "\n".join(lines)


def format_srt_time(seconds: float) -> str:
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def format_clock(seconds: float) -> str:
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"


def build_manifest(info: dict[str, Any], *, url: str, title: str, uploader: str, video_id: str) -> dict[str, Any]:
    return {
        "url": url,
        "title": title,
        "uploader": uploader,
        "video_id": video_id,
        "webpage_url": info.get("webpage_url"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "description": info.get("description"),
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def first_text(data: dict[str, Any], *keys: str, default: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def safe_name(value: str, *, max_length: int = 120) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        cleaned = "untitled"
    return cleaned[:max_length].rstrip(" .")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", strip_tags(value)).strip()


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)
