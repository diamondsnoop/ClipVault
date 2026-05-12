from __future__ import annotations

from pathlib import Path

import pytest

from clipvault.auth import (
    apply_ytdlp_cookies,
    build_authenticated_opener,
    clear_cookie_cache,
    resolve_cookies_path,
)

AUTH_SENTINEL = "__clipvault_auth__"


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("clipvault.auth._cached_clipvault_cookie_path", None)


def test_resolve_cookies_path_disabled() -> None:
    assert resolve_cookies_path(None) is None
    assert resolve_cookies_path(False) is None
    assert resolve_cookies_path(0) is None


def test_resolve_cookies_path_auto_generates_cookie_file(tmp_path: Path, monkeypatch):
    auth_toml = tmp_path / "auth.toml"
    auth_toml.write_text(
        '[bilibili]\n'
        'sessdata = "abc123"\n'
        'bili_jct = "def456"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("clipvault.credentials.get_config_dir", lambda: tmp_path)

    result = resolve_cookies_path(AUTH_SENTINEL)

    assert result is not None
    assert result.is_file()
    content = result.read_text(encoding="utf-8")
    assert "SESSDATA\tabc123" in content
    assert "bili_jct\tdef456" in content


def test_resolve_cookies_path_auto_missing_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("clipvault.credentials.get_config_dir", lambda: tmp_path)

    with pytest.raises(RuntimeError, match="未找到 ClipVault 凭据文件"):
        resolve_cookies_path(AUTH_SENTINEL)


def test_resolve_cookies_path_auto_empty_credentials(tmp_path: Path, monkeypatch):
    auth_toml = tmp_path / "auth.toml"
    auth_toml.write_text("# empty\n", encoding="utf-8")
    monkeypatch.setattr("clipvault.credentials.get_config_dir", lambda: tmp_path)

    with pytest.raises(RuntimeError, match="未找到任何凭据"):
        resolve_cookies_path(AUTH_SENTINEL)


def test_resolve_cookies_path_auto_caches_result(tmp_path: Path, monkeypatch):
    auth_toml = tmp_path / "auth.toml"
    auth_toml.write_text('[bilibili]\nsessdata = "abc"\n', encoding="utf-8")
    monkeypatch.setattr("clipvault.credentials.get_config_dir", lambda: tmp_path)

    path1 = resolve_cookies_path(AUTH_SENTINEL)
    path2 = resolve_cookies_path(AUTH_SENTINEL)
    assert path1 == path2


def test_resolve_cookies_path_with_file(tmp_path: Path):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text(
        ".bilibili.com\tTRUE\t/\tFALSE\t2147483647\tSESSDATA\tabc\n",
        encoding="utf-8",
    )

    result = resolve_cookies_path(str(cookie_file))

    assert result == cookie_file


def test_resolve_cookies_path_with_file_not_found():
    with pytest.raises(RuntimeError, match="未找到 cookies 文件"):
        resolve_cookies_path("C:\\nonexistent\\cookies.txt")


def test_apply_ytdlp_cookies_sets_cookiefile(tmp_path: Path, monkeypatch, capsys):
    auth_toml = tmp_path / "auth.toml"
    auth_toml.write_text('[bilibili]\nsessdata = "abc"\n', encoding="utf-8")
    monkeypatch.setattr("clipvault.credentials.get_config_dir", lambda: tmp_path)
    opts: dict[str, object] = {}

    apply_ytdlp_cookies(opts, AUTH_SENTINEL)

    assert "cookiefile" in opts
    assert Path(str(opts["cookiefile"])).is_file()
    assert "已启用 cookies 文件" in capsys.readouterr().err


def test_apply_ytdlp_cookies_skipped_when_disabled(opts: dict[str, object] | None = None) -> None:
    opts = opts or {}
    apply_ytdlp_cookies(opts, None)
    assert "cookiefile" not in opts


def test_build_authenticated_opener_loads_cookie_file(tmp_path: Path, monkeypatch, capsys):
    auth_toml = tmp_path / "auth.toml"
    auth_toml.write_text('[bilibili]\nsessdata = "abc"\n', encoding="utf-8")
    monkeypatch.setattr("clipvault.credentials.get_config_dir", lambda: tmp_path)

    opener = build_authenticated_opener(AUTH_SENTINEL)

    assert hasattr(opener, "open")
    assert "HTTP 请求已加载 cookies" in capsys.readouterr().err


def test_build_authenticated_opener_skipped_when_disabled() -> None:
    opener = build_authenticated_opener(None)
    assert hasattr(opener, "open")


def test_clear_cookie_cache_deletes_file(tmp_path: Path, monkeypatch):
    auth_toml = tmp_path / "auth.toml"
    auth_toml.write_text('[bilibili]\nsessdata = "abc"\n', encoding="utf-8")
    monkeypatch.setattr("clipvault.credentials.get_config_dir", lambda: tmp_path)

    path = resolve_cookies_path(AUTH_SENTINEL)
    assert path.is_file()

    clear_cookie_cache()
    assert not path.is_file()
