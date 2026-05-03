from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .library import is_completed, safe_name, write_json
from .platforms import extract_creator_entries, identify_platform


CREATOR_REGISTRY_SCHEMA_VERSION = 1


def creator_registry_path(library: Path) -> Path:
    return library / "_creators.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_id(platform: str, source_url: str) -> str:
    digest = hashlib.sha256(source_url.strip().encode("utf-8")).hexdigest()[:12]
    return f"{platform}:{digest}"


def _fallback_name(source_url: str) -> str:
    cleaned = source_url.strip().rstrip("/")
    if not cleaned:
        return "unknown creator"
    return safe_name(cleaned.split("/")[-1] or cleaned, max_length=80)


def load_creator_registry(library: Path) -> dict[str, Any]:
    path = creator_registry_path(library)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "schema_version": CREATOR_REGISTRY_SCHEMA_VERSION,
            "type": "creator_registry",
            "updated_at": None,
            "creators": [],
        }
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[creator] registry load failed ({path}): {exc}", file=sys.stderr)
        return {
            "schema_version": CREATOR_REGISTRY_SCHEMA_VERSION,
            "type": "creator_registry",
            "updated_at": None,
            "creators": [],
        }
    if not isinstance(data, dict) or not isinstance(data.get("creators"), list):
        print(f"[creator] invalid registry shape ({path}), starting empty", file=sys.stderr)
        return {
            "schema_version": CREATOR_REGISTRY_SCHEMA_VERSION,
            "type": "creator_registry",
            "updated_at": None,
            "creators": [],
        }
    return data


def list_creator_sources(library: Path) -> list[dict[str, Any]]:
    registry = load_creator_registry(library)
    creators = sorted(
        registry.get("creators", []),
        key=lambda item: (str(item.get("platform") or ""), str(item.get("name") or "")),
    )
    print(f"[creator] listed: {len(creators)}", file=sys.stderr)
    return creators


def find_creator_source(library: Path, selector: str) -> dict[str, Any]:
    selector = selector.strip()
    if not selector:
        raise ValueError("creator selector is empty")

    creators = load_creator_registry(library).get("creators", [])
    exact_id = [record for record in creators if record.get("id") == selector]
    if len(exact_id) == 1:
        return exact_id[0]

    lowered = selector.lower()
    name_matches = [
        record
        for record in creators
        if str(record.get("name") or "").lower() == lowered
        or str(record.get("source_url") or "").lower() == lowered
    ]
    if len(name_matches) == 1:
        return name_matches[0]
    if len(name_matches) > 1:
        raise ValueError(f"creator selector is ambiguous: {selector}")
    raise ValueError(f"creator source not found: {selector}")


def _processed_video_lookup(library: Path) -> tuple[set[str], set[str]]:
    video_ids: set[str] = set()
    urls: set[str] = set()
    for manifest_path in library.rglob("manifest.json"):
        video_dir = manifest_path.parent
        if not is_completed(video_dir):
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        video_id = manifest.get("video_id")
        if video_id:
            video_ids.add(str(video_id))
        for key in ("source_url", "webpage_url"):
            value = manifest.get(key)
            if value:
                urls.add(str(value).rstrip("/"))
    return video_ids, urls


def fetch_creator_videos(
    library: Path,
    *,
    selector: str,
    limit: int,
    verbose: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    registry = load_creator_registry(library)
    record = find_creator_source(library, selector)
    print(f"[creator] fetching: {record.get('name')} ({record.get('platform')})", file=sys.stderr)
    entries = extract_creator_entries(str(record["source_url"]), limit=limit, verbose=verbose)
    processed_ids, processed_urls = _processed_video_lookup(library)
    annotated_entries: list[dict[str, Any]] = []
    for entry in entries:
        annotated = dict(entry)
        entry_id = annotated.get("id")
        entry_url = str(annotated.get("url") or "").rstrip("/")
        annotated["library_status"] = (
            "processed"
            if (entry_id and str(entry_id) in processed_ids) or (entry_url and entry_url in processed_urls)
            else "new"
        )
        annotated_entries.append(annotated)
    new_count = sum(1 for entry in annotated_entries if entry["library_status"] == "new")
    processed_count = len(annotated_entries) - new_count
    print(f"[creator] candidates: {new_count} new, {processed_count} processed", file=sys.stderr)

    now = _now()
    for item in registry.get("creators", []):
        if item.get("id") == record.get("id"):
            item["last_checked_at"] = now
            break
    registry["updated_at"] = now
    path = creator_registry_path(library)
    write_json(path, registry)

    return {
        "status": "ok",
        "mode": "preview",
        "creator": record,
        "entries": annotated_entries,
        "count": len(annotated_entries),
        "new_count": new_count,
        "processed_count": processed_count,
    }


def add_creator_source(library: Path, *, source_url: str, name: str | None = None) -> dict[str, Any]:
    source_url = source_url.strip().rstrip("/")
    if not source_url:
        raise ValueError("creator source URL is empty")

    platform = identify_platform(source_url)
    if platform == "unknown":
        raise ValueError(f"unsupported or unknown creator platform: {source_url}")

    registry = load_creator_registry(library)
    record_id = _record_id(platform, source_url)
    display_name = safe_name(name.strip(), max_length=80) if name and name.strip() else _fallback_name(source_url)
    now = _now()
    record = {
        "id": record_id,
        "platform": platform,
        "name": display_name,
        "source_url": source_url,
        "added_at": now,
        "last_checked_at": None,
    }

    creators = registry.setdefault("creators", [])
    existing = next((item for item in creators if item.get("id") == record_id), None)
    if existing:
        existing.update({
            "platform": platform,
            "name": display_name,
            "source_url": source_url,
        })
        record = existing
        action = "updated"
    else:
        creators.append(record)
        action = "added"

    registry["schema_version"] = CREATOR_REGISTRY_SCHEMA_VERSION
    registry["type"] = "creator_registry"
    registry["updated_at"] = now
    creators.sort(key=lambda item: (str(item.get("platform") or ""), str(item.get("name") or "")))

    path = creator_registry_path(library)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, registry)
    print(f"[creator] {action}: {display_name} ({platform})", file=sys.stderr)
    print(f"[creator] registry: {path}", file=sys.stderr)
    return record
