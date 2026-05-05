from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .platforms import identify_platform


SCHEMA_VERSION = 1
INDEX_SCHEMA_VERSION = 1


def video_directory(library: Path, *, platform: str, uploader: str, title: str, video_id: str, series: str | None = None) -> Path:
    series = normalize_series(series)
    parts = [library, safe_name(platform), safe_name(uploader)]
    if series:
        parts.append(safe_name(series))
    parts.append(safe_name(f"{title} - {video_id}"))
    return Path(*parts)


def legacy_video_directory(library: Path, *, uploader: str, title: str, video_id: str) -> Path:
    """Old-style path without platform segment (backward compatibility)."""
    return library / safe_name(uploader) / safe_name(f"{title} - {video_id}")


def is_completed(video_dir: Path) -> bool:
    """Check whether a video directory has a completed manifest."""
    manifest_path = video_dir / "manifest.json"
    if not manifest_path.exists():
        return False
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    output_files = data.get("output_files")
    if data.get("subtitle_source") and isinstance(output_files, list) and output_files:
        return all((video_dir / str(file_name)).is_file() for file_name in output_files)

    # Legacy check: v0 manifests had no subtitle_source/output_files fields.
    expected = ("transcript.srt", "transcript.txt", "transcript.md")
    return all((video_dir / f).exists() for f in expected)


def resolve_video_directory(
    library: Path,
    *,
    platform: str,
    uploader: str,
    title: str,
    video_id: str,
    series: str | None = None,
) -> Path:
    """Resolve the video directory: prefer series path if requested,
    then new platform-aware path, then legacy path."""
    if series:
        series_dir = video_directory(library, platform=platform, uploader=uploader, title=title, video_id=video_id, series=series)
        # When series is requested, never fall back to a non-series path.
        return series_dir
    new_dir = video_directory(library, platform=platform, uploader=uploader, title=title, video_id=video_id)
    if is_completed(new_dir):
        return new_dir
    legacy_dir = legacy_video_directory(library, uploader=uploader, title=title, video_id=video_id)
    if is_completed(legacy_dir):
        return legacy_dir
    return new_dir


def build_manifest(
    info: dict[str, Any],
    *,
    url: str,
    title: str,
    uploader: str,
    video_id: str,
    series: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "title": title,
        "uploader": uploader,
        "video_id": video_id,
        "source_url": url,
        "webpage_url": info.get("webpage_url"),
        "platform": guess_platform(url),
        "series": normalize_series(series),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "description": info.get("description"),
        "creator_id": info.get("channel_id") or info.get("uploader_id"),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "subtitle_source": None,
        "asr_model": None,
        "asr_device": None,
        "output_files": [],
    }


def update_manifest(path: Path, **updates: Any) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(updates)
    write_json(path, data)


def guess_platform(url: str) -> str:
    """Identify the video platform from *url*.

    Delegates to :func:`platforms.identify_platform`.  Kept in ``library``
    so that :func:`build_manifest` and external callers have a single
    import path.
    """
    return identify_platform(url)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sort_video_entries(videos: list[dict[str, Any]]) -> None:
    """Sort video entries by processed_at descending, then title ascending."""
    videos.sort(key=lambda v: v.get("title") or "")
    videos.sort(key=lambda v: v.get("processed_at") or "", reverse=True)


def _dedupe_video_entries(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate video entries by video_id, keeping the last scanned entry."""
    deduped: dict[str, dict[str, Any]] = {}
    for video in videos:
        key = video.get("video_id")
        if not key:
            continue
        deduped[key] = video
    result = list(deduped.values())
    _sort_video_entries(result)
    return result


def creator_index_path(library: Path, *, platform: str, uploader: str) -> Path:
    """Path to the creator-level ``_index.json``."""
    return library / safe_name(platform) / safe_name(uploader) / "_index.json"


def series_index_path(library: Path, *, platform: str, uploader: str, series: str) -> Path | None:
    """Path to the series-level ``_index.json``, or ``None`` if series is blank."""
    series = normalize_series(series)
    if not series:
        return None
    return library / safe_name(platform) / safe_name(uploader) / safe_name(series) / "_index.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _video_entry(manifest: dict[str, Any], *, relative_path: str) -> dict[str, Any]:
    """Build a video entry dict from manifest fields."""
    return {
        "video_id": manifest.get("video_id", ""),
        "title": manifest.get("title", ""),
        "series": normalize_series(manifest.get("series")),
        "relative_path": relative_path,
        "source_url": manifest.get("source_url", ""),
        "subtitle_source": manifest.get("subtitle_source"),
        "duration": manifest.get("duration"),
        "upload_date": manifest.get("upload_date"),
        "processed_at": manifest.get("processed_at", ""),
    }


def update_library_indexes(video_dir: Path, manifest: dict[str, Any], library: Path) -> None:
    """Update (create or upsert) the creator and series ``_index.json`` files.

    Called after every completed pipeline run (both new and cached)
    so that the library stays self-describing without a separate indexing pass.

    * Creator index is always created/updated.
    * Series index is created/updated only when ``manifest["series"]`` is set.
    * Videos are deduplicated by ``video_id`` — later runs overwrite earlier entries.
    * Indexes are sorted by ``processed_at`` descending, then title ascending.
    """
    platform = manifest.get("platform")
    uploader = manifest.get("uploader")
    video_id = manifest.get("video_id")
    if not platform or not uploader or not video_id:
        return

    series = normalize_series(manifest.get("series"))
    now = datetime.now(timezone.utc).isoformat()

    # Build relative path for creator index
    video_folder = video_dir.name
    relative_path = f"{safe_name(series)}/{video_folder}" if series else video_folder

    entry = _video_entry(manifest, relative_path=relative_path)

    # ── Creator index ──────────────────────────────────────────────
    c_path = creator_index_path(library, platform=platform, uploader=uploader)
    c_path.parent.mkdir(parents=True, exist_ok=True)

    c_index = _load_json(c_path)
    if not c_index.get("schema_version"):
        c_index = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "type": "creator",
            "platform": platform,
            "creator": uploader,
            "updated_at": now,
            "series": [],
            "videos": [],
        }

    # Upsert video entry
    existing: dict[str, int] = {v.get("video_id"): i for i, v in enumerate(c_index.get("videos", []))}
    if video_id in existing:
        c_index["videos"][existing[video_id]] = entry
    else:
        c_index["videos"].append(entry)

    # Rebuild series aggregation (null series are not included)
    agg: dict[str, dict[str, Any]] = {}
    for v in c_index["videos"]:
        s = normalize_series(v.get("series"))
        if not s:
            continue
        if s not in agg:
            agg[s] = {"count": 0, "latest": ""}
        agg[s]["count"] += 1
        pt = v.get("processed_at") or ""
        if pt > agg[s]["latest"]:
            agg[s]["latest"] = pt

    c_index["series"] = [
        {"name": s_name, "video_count": info["count"], "latest_processed_at": info["latest"]}
        for s_name, info in sorted(agg.items(), key=lambda x: x[0])
    ]
    # Sort: processed_at descending, then title ascending (stable sort)
    _sort_video_entries(c_index["videos"])
    c_index["updated_at"] = now

    write_json(c_path, c_index)
    print(f"[index] creator: {c_path}", file=sys.stderr)

    # ── Series index ───────────────────────────────────────────────
    if not series:
        return

    s_path = series_index_path(library, platform=platform, uploader=uploader, series=series)
    if s_path is None:
        return
    s_path.parent.mkdir(parents=True, exist_ok=True)

    s_index = _load_json(s_path)
    if not s_index.get("schema_version"):
        s_index = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "type": "series",
            "platform": platform,
            "creator": uploader,
            "series": series,
            "updated_at": now,
            "video_count": 0,
            "videos": [],
        }

    series_entry = dict(entry)
    series_entry["relative_path"] = video_folder  # relative to series root

    existing_sv: dict[str, int] = {v.get("video_id"): i for i, v in enumerate(s_index.get("videos", []))}
    if video_id in existing_sv:
        s_index["videos"][existing_sv[video_id]] = series_entry
    else:
        s_index["videos"].append(series_entry)

    _sort_video_entries(s_index["videos"])
    s_index["video_count"] = len(s_index["videos"])
    s_index["updated_at"] = now

    write_json(s_path, s_index)
    print(f"[index] series: {s_path}", file=sys.stderr)


def _required_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if value is None or not str(value).strip():
        raise ValueError(f"missing required field: {field}")
    return str(value).strip()


def _manifest_video_entries(
    library: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    platform = _required_text(manifest, "platform")
    uploader = _required_text(manifest, "uploader")
    _required_text(manifest, "video_id")
    series = normalize_series(manifest.get("series"))

    video_dir = manifest_path.parent
    creator_root = library / safe_name(platform) / safe_name(uploader)
    try:
        creator_relative = video_dir.relative_to(creator_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"manifest is outside expected creator path: {creator_root}") from exc

    creator_entry = _video_entry(manifest, relative_path=creator_relative)
    if not series:
        return creator_entry, None

    series_root = creator_root / safe_name(series)
    try:
        series_relative = video_dir.relative_to(series_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"manifest is outside expected series path: {series_root}") from exc

    series_entry = dict(creator_entry)
    series_entry["relative_path"] = series_relative
    return creator_entry, series_entry


def rebuild_library_indexes(library: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Rebuild creator and series indexes from completed manifests.

    This is a full rebuild: desired indexes are generated from current
    ``manifest.json`` files, and stale ``_index.json`` files are removed
    when ``dry_run`` is false.
    """
    print(f"[library] scanning: {library}", file=sys.stderr)
    now = datetime.now(timezone.utc).isoformat()
    existing_indexes = {path for path in library.rglob("_index.json") if path.is_file()}
    creator_videos: dict[tuple[str, str], list[dict[str, Any]]] = {}
    series_videos: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    manifests_seen = 0
    skipped: list[dict[str, str]] = []

    for manifest_path in sorted(library.rglob("manifest.json")):
        manifests_seen += 1
        video_dir = manifest_path.parent
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest must be a JSON object")
            if not is_completed(video_dir):
                raise ValueError("manifest is incomplete or output files are missing")
            platform = _required_text(manifest, "platform")
            uploader = _required_text(manifest, "uploader")
            series = normalize_series(manifest.get("series"))
            creator_entry, series_entry = _manifest_video_entries(library, manifest_path, manifest)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"[index] skipped manifest ({manifest_path}): {exc}", file=sys.stderr)
            skipped.append({"path": str(manifest_path), "reason": str(exc)})
            continue

        creator_key = (platform, uploader)
        creator_videos.setdefault(creator_key, []).append(creator_entry)
        if series and series_entry:
            series_videos.setdefault((platform, uploader, series), []).append(series_entry)

    desired_indexes: dict[Path, dict[str, Any]] = {}
    for (platform, uploader), videos in sorted(creator_videos.items()):
        videos = _dedupe_video_entries(videos)
        series_agg: dict[str, dict[str, Any]] = {}
        for video in videos:
            series = normalize_series(video.get("series"))
            if not series:
                continue
            if series not in series_agg:
                series_agg[series] = {"count": 0, "latest": ""}
            series_agg[series]["count"] += 1
            processed_at = video.get("processed_at") or ""
            if processed_at > series_agg[series]["latest"]:
                series_agg[series]["latest"] = processed_at

        desired_indexes[creator_index_path(library, platform=platform, uploader=uploader)] = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "type": "creator",
            "platform": platform,
            "creator": uploader,
            "updated_at": now,
            "series": [
                {"name": name, "video_count": info["count"], "latest_processed_at": info["latest"]}
                for name, info in sorted(series_agg.items(), key=lambda item: item[0])
            ],
            "videos": videos,
        }

    for (platform, uploader, series), videos in sorted(series_videos.items()):
        videos = _dedupe_video_entries(videos)
        path = series_index_path(library, platform=platform, uploader=uploader, series=series)
        if path is None:
            continue
        desired_indexes[path] = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "type": "series",
            "platform": platform,
            "creator": uploader,
            "series": series,
            "updated_at": now,
            "video_count": len(videos),
            "videos": videos,
        }

    stale_indexes = sorted(existing_indexes - set(desired_indexes))
    if dry_run:
        print(
            f"[index] dry-run: would write {len(desired_indexes)} indexes, remove {len(stale_indexes)} stale indexes",
            file=sys.stderr,
        )
    else:
        for path, data in sorted(desired_indexes.items(), key=lambda item: str(item[0])):
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, data)
            if data.get("type") == "creator":
                print(f"[index] rebuilt creator: {path}", file=sys.stderr)
            else:
                print(f"[index] rebuilt series: {path}", file=sys.stderr)
        for path in stale_indexes:
            try:
                path.unlink()
                print(f"[index] removed stale: {path}", file=sys.stderr)
            except OSError as exc:
                print(f"[index] failed removing stale ({path}): {exc}", file=sys.stderr)

    return {
        "status": "ok",
        "library": str(library),
        "dry_run": dry_run,
        "manifests_seen": manifests_seen,
        "videos_indexed": sum(
            len(index["videos"])
            for index in desired_indexes.values()
            if index.get("type") == "creator"
        ),
        "skipped_manifests": skipped,
        "indexes": [str(path) for path in sorted(desired_indexes)],
        "stale_indexes": [str(path) for path in stale_indexes],
    }


def first_text(data: dict[str, Any], *keys: str, default: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def normalize_series(series: str | None) -> str | None:
    """Normalize a user-provided series name.

    * ``None``, empty, or whitespace-only → ``None``.
    * Otherwise → stripped of leading/trailing whitespace.
    """
    if series is None:
        return None
    stripped = series.strip()
    return stripped if stripped else None


def safe_name(value: str, *, max_length: int = 120) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        cleaned = "untitled"
    return cleaned[:max_length].rstrip(" .")
