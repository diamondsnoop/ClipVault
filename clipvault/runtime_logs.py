from __future__ import annotations

import sys


_STAGE_LABELS = {
    "asr": "ASR",
    "audio": "音频",
    "auth": "认证",
    "cache": "缓存",
    "creator": "创作者",
    "error": "错误",
    "export": "导出",
    "index": "索引",
    "library": "仓库",
    "metadata": "元数据",
    "pipeline": "流程",
    "platform": "平台",
    "queue": "队列",
    "series": "系列",
    "settings": "设置",
    "subtitle": "字幕",
    "ui": "界面",
}

_LEVEL_LABELS = {
    "error": "错误",
    "success": "成功",
    "warning": "警告",
}


def format_log(stage: str, message: str, *, level: str = "info") -> str:
    tags: list[str] = []
    level_label = _LEVEL_LABELS.get(level)
    if level_label:
        tags.append(level_label)
    tags.append(_STAGE_LABELS.get(stage, stage))
    prefix = "".join(f"[{tag}]" for tag in tags if tag)
    return f"{prefix} {message}"


def emit_log(stage: str, message: str, *, level: str = "info") -> None:
    print(format_log(stage, message, level=level), file=sys.stderr)
