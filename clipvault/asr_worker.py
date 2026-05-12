from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from .asr import add_nvidia_dll_directories
from .text import clean_text

add_nvidia_dll_directories()

from faster_whisper import WhisperModel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ClipVault GPU ASR worker")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--compute-type", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    add_nvidia_dll_directories()

    model = None
    segments_iter = None
    info = None

    try:
        model = WhisperModel(
            args.model,
            device=args.device,
            compute_type=args.compute_type,
            local_files_only=True,
        )
        segments_iter, info = model.transcribe(
            args.audio,
            language="zh",
            vad_filter=True,
            beam_size=5,
        )
        segments: list[dict[str, object]] = []
        for segment in segments_iter:
            text = clean_text(segment.text)
            if text:
                segments.append(
                    {
                        "start": float(segment.start),
                        "end": float(segment.end),
                        "text": text,
                    }
                )

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps({"segments": segments}, ensure_ascii=False),
            encoding="utf-8",
        )
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
