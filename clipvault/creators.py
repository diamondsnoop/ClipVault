from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .library import safe_name, write_json
from .platforms import identify_platform


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
