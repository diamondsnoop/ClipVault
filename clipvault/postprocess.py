from __future__ import annotations

from functools import lru_cache

from .models import SubtitleSegment


@lru_cache(maxsize=1)
def _opencc_t2s() -> object:
    try:
        from opencc import OpenCC
    except ImportError as exc:
        raise RuntimeError(
            "中文繁转简功能依赖 `opencc-python-reimplemented`。"
            "请先安装 requirements.lock 中的依赖。"
        ) from exc
    return OpenCC("t2s")


def simplify_chinese_text(text: str) -> str:
    converter = _opencc_t2s()
    return str(converter.convert(text))


def simplify_chinese_segments(segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
    return [
        SubtitleSegment(
            start=segment.start,
            end=segment.end,
            text=simplify_chinese_text(segment.text),
        )
        for segment in segments
    ]
