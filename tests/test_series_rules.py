from __future__ import annotations

import json
from pathlib import Path

from clipvault.series_rules import (
    load_series_rules,
    match_series_from_title,
    resolve_series,
    series_rules_path,
)


# ── series_rules_path ───────────────────────────────────────────────────


def test_series_rules_path():
    path = series_rules_path(Path("/lib"), platform="youtube", uploader="Jabzy")
    assert path == Path("/lib/youtube/Jabzy/_series_rules.json")


# ── load_series_rules ───────────────────────────────────────────────────


def test_load_rules_success(tmp_path: Path):
    rules_file = tmp_path / "_series_rules.json"
    rules_file.write_text(
        json.dumps({
            "schema_version": 1,
            "rules": [{"series": "S1", "title_contains": ["hello"], "title_regex": None}],
        }),
        encoding="utf-8",
    )
    rules = load_series_rules(rules_file)
    assert rules is not None
    assert len(rules) == 1
    assert rules[0]["series"] == "S1"


def test_load_rules_not_found(tmp_path: Path):
    rules_file = tmp_path / "nonexistent.json"
    assert load_series_rules(rules_file) is None


def test_load_rules_bad_json(tmp_path: Path, capsys):
    rules_file = tmp_path / "_series_rules.json"
    rules_file.write_text("not-json", encoding="utf-8")
    result = load_series_rules(rules_file)
    assert result is None
    stderr = capsys.readouterr().err
    assert "读取规则文件失败" in stderr


def test_load_rules_not_a_dict(tmp_path: Path):
    rules_file = tmp_path / "_series_rules.json"
    rules_file.write_text("[]", encoding="utf-8")
    assert load_series_rules(rules_file) is None


def test_load_rules_rules_not_a_list(tmp_path: Path):
    rules_file = tmp_path / "_series_rules.json"
    rules_file.write_text(
        json.dumps({"schema_version": 1, "rules": "not-a-list"}),
        encoding="utf-8",
    )
    assert load_series_rules(rules_file) is None


# ── match_series_from_title ────────────────────────────────────────────


def test_match_title_contains_hit():
    rules = [{"series": "睡前消息", "title_contains": ["睡前消息"], "title_regex": None}]
    assert match_series_from_title("睡前消息 2026-01-01", rules) == "睡前消息"


def test_match_title_contains_no_hit():
    rules = [{"series": "睡前消息", "title_contains": ["睡前消息"], "title_regex": None}]
    assert match_series_from_title("Some Other Video", rules) is None


def test_match_title_regex_hit():
    rules = [{"series": "History", "title_contains": [], "title_regex": r"History of"}]
    assert match_series_from_title("History of the Middle East", rules) == "History"


def test_match_title_regex_no_hit():
    rules = [{"series": "History", "title_contains": [], "title_regex": r"History of"}]
    assert match_series_from_title("Something Else", rules) is None


def test_match_first_rule_wins():
    rules = [
        {"series": "First", "title_contains": ["common"], "title_regex": None},
        {"series": "Second", "title_contains": ["common"], "title_regex": None},
    ]
    assert match_series_from_title("common video", rules) == "First"


def test_match_empty_series_rule_skipped():
    rules = [
        {"series": "", "title_contains": ["hello"], "title_regex": None},
        {"series": "Real", "title_contains": ["hello"], "title_regex": None},
    ]
    assert match_series_from_title("hello world", rules) == "Real"


def test_match_blank_series_rule_skipped():
    rules = [
        {"series": "   ", "title_contains": ["hello"], "title_regex": None},
        {"series": "Real", "title_contains": ["hello"], "title_regex": None},
    ]
    assert match_series_from_title("hello world", rules) == "Real"


def test_match_empty_rule_skipped():
    """Rule with no title_contains and no title_regex is ignored."""
    rules = [
        {"series": "Skipped", "title_contains": [], "title_regex": None},
        {"series": "Real", "title_contains": ["hello"], "title_regex": None},
    ]
    assert match_series_from_title("hello world", rules) == "Real"


def test_match_invalid_regex_skipped(capsys):
    rules = [
        {"series": "Bad", "title_contains": [], "title_regex": r"[invalid"},
        {"series": "Good", "title_contains": ["hello"], "title_regex": None},
    ]
    result = match_series_from_title("hello world", rules)
    assert result == "Good"
    stderr = capsys.readouterr().err
    assert "正则无效" in stderr


def test_match_contains_and_regex_both_work():
    """title_contains alone is sufficient when title_regex is None."""
    rules = [{"series": "S1", "title_contains": ["hello"], "title_regex": None}]
    assert match_series_from_title("hello world", rules) == "S1"


def test_match_regex_without_contains():
    """title_regex alone is sufficient when title_contains is empty."""
    rules = [{"series": "S1", "title_contains": [], "title_regex": r"^\d{4}"}]
    assert match_series_from_title("2026 Video", rules) == "S1"
    assert match_series_from_title("Video 2026", rules) is None


# ── resolve_series ──────────────────────────────────────────────────────


def test_resolve_manual_priority(tmp_path: Path):
    """explicit series returns (series, 'manual') immediately, ignores rules."""
    (tmp_path / "youtube" / "U").mkdir(parents=True)
    rules_file = tmp_path / "youtube" / "U" / "_series_rules.json"
    rules_file.write_text(
        json.dumps({
            "rules": [{"series": "Auto", "title_contains": ["video"], "title_regex": None}],
        }),
        encoding="utf-8",
    )
    series, source = resolve_series(
        tmp_path, platform="youtube", uploader="U", title="my video", explicit_series="Manual",
    )
    assert series == "Manual"
    assert source == "manual"


def test_resolve_auto_match(tmp_path: Path, capsys):
    """No explicit series, rule matches -> (series, 'rule')."""
    (tmp_path / "youtube" / "U").mkdir(parents=True)
    rules_file = tmp_path / "youtube" / "U" / "_series_rules.json"
    rules_file.write_text(
        json.dumps({
            "rules": [{"series": "Auto", "title_contains": ["video"], "title_regex": None}],
        }),
        encoding="utf-8",
    )
    series, source = resolve_series(
        tmp_path, platform="youtube", uploader="U", title="my video title", explicit_series=None,
    )
    assert series == "Auto"
    assert source == "rule"
    stderr = capsys.readouterr().err
    assert "自动匹配到系列：Auto" in stderr


def test_resolve_no_match(tmp_path: Path):
    """No explicit series, no rule matches -> (None, None)."""
    (tmp_path / "youtube" / "U").mkdir(parents=True)
    rules_file = tmp_path / "youtube" / "U" / "_series_rules.json"
    rules_file.write_text(
        json.dumps({
            "rules": [{"series": "Auto", "title_contains": ["xyz"], "title_regex": None}],
        }),
        encoding="utf-8",
    )
    series, source = resolve_series(
        tmp_path, platform="youtube", uploader="U", title="my video", explicit_series=None,
    )
    assert series is None
    assert source is None


def test_resolve_no_rules_file(tmp_path: Path):
    """No rules file -> (None, None), no crash."""
    series, source = resolve_series(
        tmp_path, platform="youtube", uploader="U", title="anything", explicit_series=None,
    )
    assert series is None
    assert source is None


def test_resolve_blank_explicit_is_auto(tmp_path: Path):
    """--series '   ' is treated as no explicit series, falls through to rules."""
    (tmp_path / "youtube" / "U").mkdir(parents=True)
    rules_file = tmp_path / "youtube" / "U" / "_series_rules.json"
    rules_file.write_text(
        json.dumps({
            "rules": [{"series": "Auto", "title_contains": ["video"], "title_regex": None}],
        }),
        encoding="utf-8",
    )
    series, source = resolve_series(
        tmp_path, platform="youtube", uploader="U", title="my video", explicit_series="   ",
    )
    assert series == "Auto"
    assert source == "rule"


# ── Malformed rule hardening (review fix) ──────────────────────────────


def test_match_skips_non_dict_rule(tmp_path: Path):
    """A bare integer in rules is skipped; the next valid rule still matches."""
    rules: list = [
        123,
        {"series": "Valid", "title_contains": ["hello"], "title_regex": None},
    ]
    assert match_series_from_title("hello world", rules) == "Valid"


def test_match_skips_non_dict_rule_log(capsys):
    """Skipping a non-dict rule prints a diagnostic."""
    rules: list = [
        "not-a-rule",
        {"series": "Valid", "title_contains": ["hello"], "title_regex": None},
    ]
    match_series_from_title("hello world", rules)
    stderr = capsys.readouterr().err
    assert "已跳过无效规则" in stderr


def test_match_various_non_dict_items_never_crash():
    """Non-dict items of various types are skipped without exception."""
    rules: list = [
        None,
        "string",
        42,
        3.14,
        [1, 2, 3],
        True,
        {"series": "S", "title_contains": ["ok"], "title_regex": None},
    ]
    assert match_series_from_title("ok", rules) == "S"
    assert match_series_from_title("nope", rules) is None


def test_load_rules_not_a_dict_logs(tmp_path: Path, capsys):
    """Top-level array logs a specific diagnostic."""
    rules_file = tmp_path / "_series_rules.json"
    rules_file.write_text("[]", encoding="utf-8")
    assert load_series_rules(rules_file) is None
    stderr = capsys.readouterr().err
    assert "顶层必须是对象" in stderr


def test_load_rules_not_a_list_logs(tmp_path: Path, capsys):
    """rules field that is not a list logs a specific diagnostic."""
    rules_file = tmp_path / "_series_rules.json"
    rules_file.write_text(
        json.dumps({"schema_version": 1, "rules": "oops"}),
        encoding="utf-8",
    )
    assert load_series_rules(rules_file) is None
    stderr = capsys.readouterr().err
    assert "rules 必须是数组" in stderr


def test_resolve_series_with_malformed_rule(tmp_path: Path, capsys):
    """A malformed rule item in the file does not crash resolve_series;
    the next valid rule is matched."""
    (tmp_path / "youtube" / "U").mkdir(parents=True)
    rules_file = tmp_path / "youtube" / "U" / "_series_rules.json"
    rules_file.write_text(
        json.dumps({
            "rules": [
                123,
                {"series": "Good", "title_contains": ["video"], "title_regex": None},
            ],
        }),
        encoding="utf-8",
    )
    series, source = resolve_series(
        tmp_path, platform="youtube", uploader="U", title="my video", explicit_series=None,
    )
    assert series == "Good"
    assert source == "rule"
    stderr = capsys.readouterr().err
    assert "已跳过无效规则" in stderr
