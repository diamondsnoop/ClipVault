from __future__ import annotations

import json
from pathlib import Path

import pytest

from clipvault.creators import (
    add_creator_source,
    creator_registry_path,
    enqueue_creator_videos,
    fetch_creator_videos,
    find_creator_source,
    job_queue_path,
    list_creator_sources,
    load_creator_registry,
    load_job_queue,
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


def test_find_creator_source_by_id_name_and_url(tmp_path: Path):
    record = add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy", name="Jabzy")

    assert find_creator_source(tmp_path, record["id"])["id"] == record["id"]
    assert find_creator_source(tmp_path, "jabzy")["id"] == record["id"]
    assert find_creator_source(tmp_path, "https://www.youtube.com/@jabzy")["id"] == record["id"]


def test_fetch_creator_videos_preview_updates_checked_at(tmp_path: Path, monkeypatch):
    add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy", name="Jabzy")

    def fake_extract_creator_entries(url: str, *, limit: int, verbose: bool):
        assert url == "https://www.youtube.com/@Jabzy"
        assert limit == 2
        assert verbose is False
        return [
            {"id": "v1", "title": "One", "url": "https://youtube.com/watch?v=v1"},
            {"id": "v2", "title": "Two", "url": "https://youtube.com/watch?v=v2"},
        ]

    monkeypatch.setattr("clipvault.creators.extract_creator_entries", fake_extract_creator_entries)

    result = fetch_creator_videos(tmp_path, selector="Jabzy", limit=2)

    assert result["status"] == "ok"
    assert result["mode"] == "preview"
    assert result["count"] == 2
    assert result["new_count"] == 2
    assert result["processed_count"] == 0
    registry = load_creator_registry(tmp_path)
    assert registry["creators"][0]["last_checked_at"] is not None


def test_fetch_creator_videos_marks_processed_entries(tmp_path: Path, monkeypatch):
    from clipvault.library import video_directory, write_json

    add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy", name="Jabzy")
    video_dir = video_directory(tmp_path, platform="youtube", uploader="Jabzy", title="One", video_id="v1")
    video_dir.mkdir(parents=True)
    write_json(
        video_dir / "manifest.json",
        {
            "schema_version": 1,
            "platform": "youtube",
            "uploader": "Jabzy",
            "title": "One",
            "video_id": "v1",
            "source_url": "https://youtube.com/watch?v=v1",
            "subtitle_source": "subtitle:en:json3",
            "output_files": ["transcript.srt", "transcript.txt", "transcript.md"],
        },
    )
    (video_dir / "transcript.srt").write_text("", encoding="utf-8")
    (video_dir / "transcript.txt").write_text("", encoding="utf-8")
    (video_dir / "transcript.md").write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "clipvault.creators.extract_creator_entries",
        lambda url, *, limit, verbose: [
            {"id": "v1", "title": "One", "url": "https://youtube.com/watch?v=v1"},
            {"id": "v2", "title": "Two", "url": "https://youtube.com/watch?v=v2"},
        ],
    )

    result = fetch_creator_videos(tmp_path, selector="Jabzy", limit=2)

    assert result["processed_count"] == 1
    assert result["new_count"] == 1
    assert [entry["library_status"] for entry in result["entries"]] == ["processed", "new"]


def test_fetch_creator_videos_rejects_bad_limit(tmp_path: Path):
    add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy", name="Jabzy")

    with pytest.raises(ValueError, match="limit"):
        fetch_creator_videos(tmp_path, selector="Jabzy", limit=0)


def test_enqueue_creator_videos_adds_new_entries(tmp_path: Path, monkeypatch):
    add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy", name="Jabzy")
    monkeypatch.setattr(
        "clipvault.creators.extract_creator_entries",
        lambda url, *, limit, verbose: [
            {"id": "v1", "title": "One", "url": "https://youtube.com/watch?v=v1"},
            {"id": "v2", "title": "Two", "url": "https://youtube.com/watch?v=v2"},
        ],
    )

    result = enqueue_creator_videos(tmp_path, selector="Jabzy", limit=2)

    assert result["added_count"] == 2
    assert job_queue_path(tmp_path).exists()
    queue = load_job_queue(tmp_path)
    assert [job["status"] for job in queue["jobs"]] == ["pending", "pending"]
    assert [job["source_url"] for job in queue["jobs"]] == [
        "https://youtube.com/watch?v=v1",
        "https://youtube.com/watch?v=v2",
    ]


def test_enqueue_creator_videos_skips_processed_and_existing(tmp_path: Path, monkeypatch):
    from clipvault.library import video_directory, write_json

    add_creator_source(tmp_path, source_url="https://www.youtube.com/@Jabzy", name="Jabzy")
    video_dir = video_directory(tmp_path, platform="youtube", uploader="Jabzy", title="One", video_id="v1")
    video_dir.mkdir(parents=True)
    write_json(
        video_dir / "manifest.json",
        {
            "schema_version": 1,
            "platform": "youtube",
            "uploader": "Jabzy",
            "title": "One",
            "video_id": "v1",
            "source_url": "https://youtube.com/watch?v=v1",
            "subtitle_source": "subtitle:en:json3",
            "output_files": ["transcript.srt", "transcript.txt", "transcript.md"],
        },
    )
    (video_dir / "transcript.srt").write_text("", encoding="utf-8")
    (video_dir / "transcript.txt").write_text("", encoding="utf-8")
    (video_dir / "transcript.md").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "clipvault.creators.extract_creator_entries",
        lambda url, *, limit, verbose: [
            {"id": "v1", "title": "One", "url": "https://youtube.com/watch?v=v1"},
            {"id": "v2", "title": "Two", "url": "https://youtube.com/watch?v=v2"},
        ],
    )

    first = enqueue_creator_videos(tmp_path, selector="Jabzy", limit=2)
    second = enqueue_creator_videos(tmp_path, selector="Jabzy", limit=2)

    assert first["added_count"] == 1
    assert first["skipped_processed"] == 1
    assert second["added_count"] == 0
    assert second["skipped_existing"] == 1
    queue = load_job_queue(tmp_path)
    assert len(queue["jobs"]) == 1


def test_load_job_queue_invalid_shape_is_non_blocking(tmp_path: Path, capsys):
    job_queue_path(tmp_path).write_text("[]", encoding="utf-8")

    queue = load_job_queue(tmp_path)

    assert queue["jobs"] == []
    assert "invalid queue shape" in capsys.readouterr().err
