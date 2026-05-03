from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from .library import normalize_series, safe_name


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
        print(f"[series] rule load failed ({path}): {exc}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        print(f"[series] invalid rules file ({path}): expected object", file=sys.stderr)
        return None
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        print(f"[series] invalid rules file ({path}): rules must be a list", file=sys.stderr)
        return None
    return rules


def match_series_from_title(title: str, rules: list[dict[str, Any]]) -> str | None:
    """Match *title* against a list of rule dicts.

    Returns the first matching series name, or ``None``.
    """
    for rule in rules:
        if not isinstance(rule, dict):
            print("[series] invalid rule skipped: expected object", file=sys.stderr)
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
                print(f"[series] invalid regex in rule '{series}': {exc}", file=sys.stderr)
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
        print(f"[series] auto: {matched}", file=sys.stderr)
        return matched, "rule"

    return None, None
