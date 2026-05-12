from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .library import normalize_series, safe_name
from .runtime_logs import emit_log


def series_rules_path(library: Path, *, platform: str, uploader: str) -> Path:
    """Path to the series rules file for a creator."""
    return library / safe_name(platform) / safe_name(uploader) / "_series_rules.json"


def load_series_rules(path: Path) -> list[dict[str, Any]] | None:
    """Load rules from ``_series_rules.json``.

    Returns ``None`` when the file does not exist or cannot be parsed
    (the caller treats this as "no rules").  Logs a diagnostic message
    on parse failure.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as exc:
        emit_log("series", f"读取规则文件失败：{path}（{exc}）", level="warning")
        return None

    if not isinstance(data, dict):
        emit_log("series", f"规则文件格式无效：{path}（顶层必须是对象）", level="warning")
        return None
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        emit_log("series", f"规则文件格式无效：{path}（rules 必须是数组）", level="warning")
        return None
    return rules


def match_series_from_title(title: str, rules: list[dict[str, Any]]) -> str | None:
    """Match *title* against a list of rule dicts.

    Returns the first matching series name, or ``None``.
    """
    for rule in rules:
        if not isinstance(rule, dict):
            emit_log("series", "已跳过无效规则：规则项必须是对象", level="warning")
            continue
        series = normalize_series(rule.get("series"))
        if not series:
            continue

        # title_contains: any keyword present in title
        has_contains = False
        contains = rule.get("title_contains")
        if isinstance(contains, list):
            for keyword in contains:
                if isinstance(keyword, str) and keyword in title:
                    has_contains = True
                    break

        # title_regex: re.search match
        has_regex = False
        regex_str = rule.get("title_regex")
        if isinstance(regex_str, str):
            try:
                if re.search(regex_str, title):
                    has_regex = True
            except re.error as exc:
                emit_log("series", f"规则 “{series}” 的正则无效：{exc}", level="warning")
                continue

        if not has_contains and not has_regex:
            continue

        return series

    return None


def resolve_series(
    library: Path,
    *,
    platform: str,
    uploader: str,
    title: str,
    explicit_series: str | None,
) -> tuple[str | None, str | None]:
    """Resolve the effective series value.

    Returns ``(series, source)`` where *source* is ``"manual"``,
    ``"rule"``, or ``None``.
    """
    series = normalize_series(explicit_series)
    if series is not None:
        return series, "manual"

    rules_path = series_rules_path(library, platform=platform, uploader=uploader)
    rules = load_series_rules(rules_path)
    if rules is None:
        return None, None

    matched = match_series_from_title(title, rules)
    if matched:
        emit_log("series", f"自动匹配到系列：{matched}", level="success")
        return matched, "rule"

    return None, None
