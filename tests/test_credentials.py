from __future__ import annotations

from pathlib import Path

import pytest

from clipvault.credentials import (
    PLATFORM_CREDENTIAL_KEYS,
    _format_toml,
    _parse_toml,
    credentials_to_netscape,
    get_auth_toml_path,
    list_credentials,
    read_credentials,
    remove_credential,
    store_credential,
)


@pytest.fixture(autouse=True)
def _patch_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("clipvault.credentials.get_config_dir", lambda: tmp_path)


# ── TOML parser / formatter ───────────────────────────────────────────


def test_parse_toml_empty():
    assert _parse_toml("") == {}
    assert _parse_toml("# comment\n") == {}


def test_parse_toml_single_section():
    raw = '[bilibili]\nsessdata = "abc"\nbili_jct = "def"\n'
    result = _parse_toml(raw)
    assert result == {"bilibili": {"sessdata": "abc", "bili_jct": "def"}}


def test_parse_toml_skips_unknown_lines():
    raw = '[bilibili]\nsessdata = "abc"\ninvalid_line\n'
    result = _parse_toml(raw)
    assert result == {"bilibili": {"sessdata": "abc"}}


def test_parse_toml_multiple_sections():
    raw = '[bilibili]\nsessdata = "x"\n\n[douyin]\nsession = "y"\n'
    result = _parse_toml(raw)
    assert result == {"bilibili": {"sessdata": "x"}, "douyin": {"session": "y"}}


def test_format_toml_roundtrip():
    data = {"bilibili": {"sessdata": "abc", "bili_jct": "def"}, "douyin": {"session": "x"}}
    raw = _format_toml(data)
    assert _parse_toml(raw) == data


def test_format_toml_empty():
    assert _format_toml({}) == ""


# ── Config path ───────────────────────────────────────────────────────


def test_get_auth_toml_path():
    path = get_auth_toml_path()
    assert path.name == "auth.toml"


# ── read / write ──────────────────────────────────────────────────────


def test_read_credentials_missing_file():
    assert read_credentials() == {}


def test_read_credentials_valid(tmp_path: Path):
    auth = tmp_path / "auth.toml"
    auth.write_text('[bilibili]\nsessdata = "abc"\n', encoding="utf-8")
    assert read_credentials() == {"bilibili": {"sessdata": "abc"}}


# ── store_credential ──────────────────────────────────────────────────


def test_store_credential_new_platform():
    path = store_credential("bilibili", sessdata="abc", bili_jct="def")
    assert path.name == "auth.toml"
    creds = read_credentials()["bilibili"]
    assert creds["sessdata"] == "abc"
    assert creds["bili_jct"] == "def"
    assert "updated_at" in creds


def test_store_credential_merge():
    store_credential("bilibili", sessdata="abc")
    store_credential("douyin", session="x")
    creds = read_credentials()
    assert creds["bilibili"]["sessdata"] == "abc"
    assert creds["douyin"]["session"] == "x"
    assert "updated_at" in creds["bilibili"]
    assert "updated_at" in creds["douyin"]


def test_store_credential_update_existing():
    store_credential("bilibili", sessdata="old")
    store_credential("bilibili", sessdata="new")
    creds = read_credentials()["bilibili"]
    assert creds["sessdata"] == "new"
    assert "updated_at" in creds


def test_store_credential_unknown_platform():
    with pytest.raises(ValueError, match="未知平台"):
        store_credential("unknown_platform", key="val")


def test_store_credential_unknown_key():
    with pytest.raises(ValueError, match="不支持凭据字段"):
        store_credential("bilibili", unknown_key="val")


# ── remove_credential ─────────────────────────────────────────────────


def test_remove_credential_exists():
    store_credential("bilibili", sessdata="abc")
    assert remove_credential("bilibili") is True
    assert "bilibili" not in read_credentials()


def test_remove_credential_missing():
    assert remove_credential("bilibili") is False


# ── list_credentials ──────────────────────────────────────────────────


def test_list_credentials_empty():
    assert list_credentials() == {}


def test_list_credentials_populated():
    store_credential("bilibili", sessdata="abc", bili_jct="def")
    store_credential("douyin", session="x")
    result = list_credentials()
    assert result == {"bilibili": ["sessdata", "bili_jct"], "douyin": ["session"]}


def test_list_credentials_hides_values():
    store_credential("bilibili", sessdata="secret123")
    result = list_credentials()
    for keys in result.values():
        for key in keys:
            assert "secret" not in key


# ── credentials_to_netscape ───────────────────────────────────────────


def test_credentials_to_netscape_bilibili():
    creds = {"sessdata": "abc", "bili_jct": "def"}
    lines = credentials_to_netscape("bilibili", creds)
    assert len(lines) == 2
    assert "SESSDATA\tabc" in lines[0]
    assert "bili_jct\tdef" in lines[1]
    assert all(".bilibili.com" in l for l in lines)


def test_credentials_to_netscape_douyin():
    lines = credentials_to_netscape("douyin", {"session": "x"})
    assert len(lines) == 1
    assert "session\tx" in lines[0]
    assert ".douyin.com" in lines[0]


def test_credentials_to_netscape_unknown_platform():
    assert credentials_to_netscape("youtube", {}) == []


def test_credentials_to_netscape_skips_empty():
    lines = credentials_to_netscape("bilibili", {"sessdata": "", "bili_jct": ""})
    assert lines == []


def test_credentials_to_netscape_partial_keys():
    lines = credentials_to_netscape("bilibili", {"sessdata": "abc"})
    assert len(lines) == 1
    assert "SESSDATA\tabc" in lines[0]
