from __future__ import annotations

import os
import sys
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
from faster_whisper import WhisperModel  # noqa: E402

from .models import SubtitleSegment
from .text import clean_text


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

