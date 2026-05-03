from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str

