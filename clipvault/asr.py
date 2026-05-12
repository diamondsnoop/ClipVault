from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
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
from faster_whisper import WhisperModel  # noqa: E402

from .models import SubtitleSegment
from .runtime_logs import emit_log
from .text import clean_text


@dataclass(slots=True)
class TranscriptionResult:
    segments: list[SubtitleSegment]
    device: str
    compute_type: str


def transcribe_audio(audio_path: Path, *, model_name: str, device: str, compute_type: str) -> TranscriptionResult:
    resolved_model = resolve_local_model(model_name)
    resolved_device = resolve_device(device)
    resolved_compute_type = resolve_compute_type(compute_type, resolved_device)
    if resolved_device == "cuda":
        _emit_transcription_start(resolved_model, resolved_device, resolved_compute_type)
        try:
            segments = _transcribe_audio_in_worker(
                audio_path,
                resolved_model=resolved_model,
                device=resolved_device,
                compute_type=resolved_compute_type,
            )
        except RuntimeError as exc:
            if device == "auto":
                emit_log("asr", f"CUDA worker 失败，将回退到 CPU：{exc}", level="warning")
                cpu_compute_type = resolve_compute_type("auto", "cpu")
                cpu_segments = transcribe_audio_once(
                    audio_path,
                    resolved_model=resolved_model,
                    device="cpu",
                    compute_type=cpu_compute_type,
                    allow_cpu_fallback=False,
                )
                return TranscriptionResult(
                    segments=cpu_segments,
                    device="cpu",
                    compute_type=cpu_compute_type,
                )
            raise
        return TranscriptionResult(
            segments=segments,
            device=resolved_device,
            compute_type=resolved_compute_type,
        )
    segments = transcribe_audio_once(
        audio_path,
        resolved_model=resolved_model,
        device=resolved_device,
        compute_type=resolved_compute_type,
        allow_cpu_fallback=(device == "auto"),
    )
    return TranscriptionResult(
        segments=segments,
        device=resolved_device,
        compute_type=resolved_compute_type,
    )


def transcribe_audio_once(
    audio_path: Path,
    *,
    resolved_model: str,
    device: str,
    compute_type: str,
    allow_cpu_fallback: bool,
) -> list[SubtitleSegment]:
    _emit_transcription_start(resolved_model, device, compute_type)
    try:
        model = WhisperModel(
            resolved_model,
            device=device,
            compute_type=compute_type,
            local_files_only=True,
        )
    except RuntimeError as exc:
        if device == "cuda" and allow_cpu_fallback:
            emit_log("asr", f"CUDA 不可用，将回退到 CPU：{exc}", level="warning")
            return transcribe_audio_once(
                audio_path,
                resolved_model=resolved_model,
                device="cpu",
                compute_type="int8",
                allow_cpu_fallback=False,
            )
        if "model" in str(exc).lower() and "not" in str(exc).lower():
            raise RuntimeError(
                f"本地不存在 ASR 模型：{resolved_model}。"
                "ClipVault 目前以 local_files_only=True 运行 faster-whisper，"
                "请先把模型下载到 Hugging Face 缓存，或通过 --model 传入本地模型目录。"
            ) from exc
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
            emit_log("asr", f"CUDA 转写失败，将回退到 CPU：{exc}", level="warning")
            return transcribe_audio_once(
                audio_path,
                resolved_model=resolved_model,
                device="cpu",
                compute_type="int8",
                allow_cpu_fallback=False,
            )
        raise
    if not segments:
        raise RuntimeError(
            "ASR 已完成，但没有返回任何文本。"
            "可能是音频静音、文件损坏，或格式不受支持。"
        )
    return segments


def _emit_transcription_start(resolved_model: str, device: str, compute_type: str) -> None:
    emit_log("asr", f"开始转写：模型={resolved_model} 设备={device} 计算类型={compute_type}")


def _transcribe_audio_in_worker(
    audio_path: Path,
    *,
    resolved_model: str,
    device: str,
    compute_type: str,
) -> list[SubtitleSegment]:
    temp_root = audio_path.parent if audio_path.parent.exists() else Path.cwd()
    work_dir = temp_root / f".clipvault-asr-worker-{uuid.uuid4().hex}"
    work_dir.mkdir(parents=True, exist_ok=False)
    try:
        result_path = work_dir / "segments.json"
        cmd = [
            sys.executable,
            "-m",
            "clipvault.asr_worker",
            "--audio",
            str(audio_path),
            "--model",
            resolved_model,
            "--device",
            device,
            "--compute-type",
            compute_type,
            "--output",
            str(result_path),
        ]
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(_summarize_worker_failure(completed))

        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError("CUDA worker 已退出，但没有写出结果文件。") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"CUDA worker 结果不是有效 JSON：{exc}") from exc

        segments = _segments_from_worker_payload(payload)
        if not segments:
            raise RuntimeError(
                "CUDA worker 已完成，但没有返回任何文本。"
                "可能是音频静音、文件损坏，或格式不受支持。"
            )
        return segments
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _segments_from_worker_payload(payload: Any) -> list[SubtitleSegment]:
    items = payload.get("segments")
    if not isinstance(items, list):
        raise RuntimeError("CUDA worker 结果缺少有效的 segments 列表。")
    segments: list[SubtitleSegment] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item["start"])
            end = float(item["end"])
            text = clean_text(str(item["text"]))
        except (KeyError, TypeError, ValueError):
            continue
        if text:
            segments.append(SubtitleSegment(start, end, text))
    return segments


def _summarize_worker_failure(completed: subprocess.CompletedProcess[str]) -> str:
    for stream in (completed.stderr, completed.stdout):
        lines = [line.strip() for line in stream.splitlines() if line.strip()]
        if lines:
            return f"退出码 {completed.returncode}：{lines[-1]}"
    return f"退出码 {completed.returncode}"


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
    emit_log("asr", f"本地缓存中未找到模型 “{model_name}”，ASR 需要本地已缓存模型", level="warning")
    return f"Systran/faster-whisper-{model_name}"
