from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from clipvault.asr import TranscriptionResult, _transcribe_audio_in_worker, transcribe_audio
from clipvault.models import SubtitleSegment


def _workspace_temp_dir() -> Path:
    root = Path.cwd() / ".tmp" / "test-asr"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"case-{uuid.uuid4().hex}"
    path.mkdir()
    return path


def test_transcribe_audio_in_worker_reads_segments():
    temp_dir = _workspace_temp_dir()
    try:
        audio_path = temp_dir / "audio.m4a"
        audio_path.write_text("audio", encoding="utf-8")

        def fake_run(cmd, **kwargs):
            output_path = Path(cmd[cmd.index("--output") + 1])
            output_path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {"start": 0.0, "end": 1.2, "text": "  你好  "},
                            {"start": 1.2, "end": 2.0, "text": "世界"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with patch("clipvault.asr.subprocess.run", side_effect=fake_run):
            segments = _transcribe_audio_in_worker(
                audio_path,
                resolved_model="resolved-model",
                device="cuda",
                compute_type="int8_float16",
            )
    finally:
        shutil.rmtree(temp_dir)

    assert segments == [
        SubtitleSegment(0.0, 1.2, "你好"),
        SubtitleSegment(1.2, 2.0, "世界"),
    ]


def test_transcribe_audio_auto_falls_back_to_cpu_when_cuda_worker_fails():
    cpu_segments = [SubtitleSegment(0.0, 1.0, "cpu fallback")]

    with (
        patch("clipvault.asr.resolve_local_model", return_value="resolved-model"),
        patch("clipvault.asr.resolve_device", return_value="cuda"),
        patch(
            "clipvault.asr.resolve_compute_type",
            side_effect=lambda compute_type, device: "int8_float16" if device == "cuda" else "int8",
        ),
        patch("clipvault.asr._transcribe_audio_in_worker", side_effect=RuntimeError("退出码 3221226505")),
        patch("clipvault.asr.transcribe_audio_once", return_value=cpu_segments) as cpu_mock,
    ):
        result = transcribe_audio(
            Path("dummy.m4a"),
            model_name="small",
            device="auto",
            compute_type="auto",
        )

    cpu_mock.assert_called_once()
    assert isinstance(result, TranscriptionResult)
    assert result.device == "cpu"
    assert result.compute_type == "int8"
    assert result.segments == cpu_segments


def test_transcribe_audio_explicit_cuda_propagates_worker_failure():
    with (
        patch("clipvault.asr.resolve_local_model", return_value="resolved-model"),
        patch("clipvault.asr.resolve_device", return_value="cuda"),
        patch("clipvault.asr.resolve_compute_type", return_value="int8_float16"),
        patch("clipvault.asr._transcribe_audio_in_worker", side_effect=RuntimeError("退出码 3221226505")),
        patch("clipvault.asr.transcribe_audio_once") as cpu_mock,
    ):
        with pytest.raises(RuntimeError, match="3221226505"):
            transcribe_audio(
                Path("dummy.m4a"),
                model_name="small",
                device="cuda",
                compute_type="auto",
            )

    cpu_mock.assert_not_called()
