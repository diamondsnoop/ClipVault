from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

PLATFORM_CREDENTIAL_KEYS: dict[str, tuple[str, ...]] = {
    "bilibili": ("sessdata", "bili_jct"),
    "douyin": ("session",),
}

_PLATFORM_COOKIE_DOMAINS: dict[str, str] = {
    "bilibili": ".bilibili.com",
    "douyin": ".douyin.com",
}

# Maps credential keys to actual Netscape cookie names (case-sensitive per RFC 6265).
_PLATFORM_COOKIE_NAMES: dict[str, dict[str, str]] = {
    "bilibili": {"sessdata": "SESSDATA", "bili_jct": "bili_jct"},
    "douyin": {"session": "session"},
}


def get_config_dir() -> Path:
    path = _fallback_config_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fallback_config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "clipvault"


def get_auth_toml_path() -> Path:
    return get_config_dir() / "auth.toml"


# ── Minimal TOML reader / writer ──────────────────────────────────────


def _parse_toml(raw: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    section: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            result.setdefault(section, {})
            continue
        if section is None:
            continue
        if "=" in stripped:
            key, _, raw_val = stripped.partition("=")
            key = key.strip()
            val = raw_val.strip().strip('"').strip("'")
            if key and val:
                result[section][key] = val
    return result


def _format_toml(data: dict[str, dict[str, str]]) -> str:
    lines: list[str] = []
    for section in sorted(data):
        lines.append(f"[{section}]")
        for key in sorted(data[section]):
            lines.append(f'{key} = "{data[section][key]}"')
        lines.append("")
    return "\n".join(lines) + "\n" if lines else ""


# ── Credential CRUD ───────────────────────────────────────────────────


def read_credentials() -> dict[str, dict[str, str]]:
    path = get_auth_toml_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    return _parse_toml(raw)


def write_credentials(data: dict[str, dict[str, str]]) -> Path:
    path = get_auth_toml_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_format_toml(data), encoding="utf-8")
    return path


def store_credential(platform: str, **kwargs: str) -> Path:
    known = PLATFORM_CREDENTIAL_KEYS.get(platform)
    if known is None:
        raise ValueError(f"unknown platform: {platform} (supported: {', '.join(PLATFORM_CREDENTIAL_KEYS)})")

    for key in kwargs:
        if key not in known:
            raise ValueError(
                f"unknown credential key '{key}' for platform '{platform}'. "
                f"Expected one of: {', '.join(known)}"
            )

    credentials = read_credentials()
    section = credentials.setdefault(platform, {})
    section.update({k: v for k, v in kwargs.items() if v})
    section["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return write_credentials(credentials)


def remove_credential(platform: str) -> bool:
    credentials = read_credentials()
    if platform not in credentials:
        return False
    del credentials[platform]
    write_credentials(credentials)
    return True


def list_credentials() -> dict[str, list[str]]:
    credentials = read_credentials()
    result: dict[str, list[str]] = {}
    for platform, keys in credentials.items():
        if platform in PLATFORM_CREDENTIAL_KEYS:
            # Only list keys we know about, never expose values
            known = PLATFORM_CREDENTIAL_KEYS[platform]
            stored = [k for k in known if k in keys]
            if stored:
                result[platform] = stored
    return result


# ── Netscape cookie generation ────────────────────────────────────────


def credentials_to_netscape(platform: str, creds: dict[str, str]) -> list[str]:
    domain = _PLATFORM_COOKIE_DOMAINS.get(platform)
    if domain is None:
        return []
    cookie_names = _PLATFORM_COOKIE_NAMES.get(platform, {})
    lines: list[str] = []
    for key, val in creds.items():
        if not val:
            continue
        cookie_name = cookie_names.get(key)
        if cookie_name is None:
            continue
        lines.append(f"{domain}\tTRUE\t/\tFALSE\t2147483647\t{cookie_name}\t{val}")
    return lines
