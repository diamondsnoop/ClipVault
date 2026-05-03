from __future__ import annotations

import json
from pathlib import Path

import pytest

from clipvault.creators import (
    add_creator_source,
    creator_registry_path,
    list_creator_sources,
    load_creator_registry,
)


def test_load_creator_registry_missing_returns_empty(tmp_path: Path):
    registry = load_creator_registry(tmp_path)

    assert registry["type"] == "creator_registry"
    assert registry["creators"] == []


def test_add_creator_source_creates_registry(tmp_path: Path):
    record = add_creator_source(
        tmp_path,
        source_url="https://www.youtube.com/@Jabzy",
        name="Jabzy",
    )

    assert record["platform"] == "youtube"
    assert record["name"] == "Jabzy"
    assert record["source_url"] == "https://www.youtube.com/@Jabzy"
    assert record["last_checked_at"] is None

    path = creator_registry_path(tmp_path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["creators"]) == 1
    assert data["creators"][0]["id"] == record["id"]


def test_add_creator_source_is_idempotent_for_same_url(tmp_path: Path):
    first = add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy", name="Old")
    second = add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy", name="New")

    data = load_creator_registry(tmp_path)
    assert len(data["creators"]) == 1
    assert first["id"] == second["id"]
    assert data["creators"][0]["name"] == "New"


def test_add_creator_source_normalizes_trailing_slash(tmp_path: Path):
    first = add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy/", name="Old")
    second = add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy", name="New")

    data = load_creator_registry(tmp_path)
    assert len(data["creators"]) == 1
    assert first["id"] == second["id"]
    assert data["creators"][0]["source_url"] == "https://www.youtube.com/@Jabzy"


def test_add_creator_source_rejects_unknown_platform(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown creator platform"):
        add_creator_source(tmp_path, source_url="https://example.com/u/test")


def test_list_creator_sources_sorted(tmp_path: Path):
    add_creator_source(tmp_path, source_url="https://www.bilibili.com/video/BV123", name="B")
    add_creator_source(tmp_path, source_url="https://www.youtube.com/@A", name="A")

    creators = list_creator_sources(tmp_path)

    assert [creator["platform"] for creator in creators] == ["bilibili", "youtube"]
    assert [creator["name"] for creator in creators] == ["B", "A"]


def test_invalid_registry_shape_is_non_blocking(tmp_path: Path, capsys):
    creator_registry_path(tmp_path).write_text("[]", encoding="utf-8")

    registry = load_creator_registry(tmp_path)

    assert registry["creators"] == []
    assert "invalid registry shape" in capsys.readouterr().err
