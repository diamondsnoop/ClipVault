from __future__ import annotations

import json
from unittest.mock import ANY

import httpx
import pytest

from clipvault.login import (
    _generate_qr_login,
    _get_cookie_value,
    _poll_qr_login,
    _show_qr_code,
    login_bilibili,
    validate_bilibili_session,
)


@pytest.fixture
def mock_client():
    """Create a real httpx client with a mock transport for API call interception."""
    return httpx.Client()


def _build_response(status_code: int, json_data: dict) -> httpx.Response:
    return httpx.Response(status_code, json=json_data, request=httpx.Request("GET", "http://mock"))


class TestGenerateQR:
    def test_success(self, mock_client, monkeypatch):
        def fake_get(url, **kw):
            return _build_response(200, {
                "code": 0,
                "data": {"url": "https://passport.bilibili.com/scan", "qrcode_key": "key_123"},
            })
        monkeypatch.setattr(mock_client, "get", fake_get)

        url, key = _generate_qr_login(mock_client)
        assert url == "https://passport.bilibili.com/scan"
        assert key == "key_123"

    def test_api_error(self, mock_client, monkeypatch):
        def fake_get(url, **kw):
            return _build_response(200, {"code": -1, "message": "error"})
        monkeypatch.setattr(mock_client, "get", fake_get)

        with pytest.raises(RuntimeError, match="二维码生成接口返回错误"):
            _generate_qr_login(mock_client)

    def test_missing_data(self, mock_client, monkeypatch):
        def fake_get(url, **kw):
            return _build_response(200, {"code": 0, "data": {}})
        monkeypatch.setattr(mock_client, "get", fake_get)

        with pytest.raises(RuntimeError, match="缺少 url 或 qrcode_key"):
            _generate_qr_login(mock_client)


def test_show_qr_code_terminal_keeps_stdout_clean(capsys):
    _show_qr_code("https://example.com/login", mode="terminal")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "请使用哔哩哔哩 App 扫描下方二维码登录" in captured.err
    assert "█" in captured.err


class TestPollQR:
    def test_not_scanned_then_confirmed(self, mock_client, monkeypatch):
        calls = []

        def fake_get(url, **kw):
            nonlocal calls
            calls.append(kw)
            if len(calls) == 1:
                return _build_response(200, {
                    "code": 0,
                    "data": {"code": 86101},
                })
            return _build_response(200, {
                "code": 0,
                "data": {"code": 0, "url": "https://passport.bilibili.com/callback?SESSDATA=abc&bili_jct=def"},
            })

        monkeypatch.setattr(mock_client, "get", fake_get)

        redirect = _poll_qr_login(mock_client, "key_123", poll_interval=0.01, timeout=10)
        assert "SESSDATA=abc" in redirect

    def test_scanned_then_confirmed(self, mock_client, monkeypatch):
        calls = []

        def fake_get(url, **kw):
            nonlocal calls
            calls.append(kw)
            if len(calls) == 1:
                return _build_response(200, {
                    "code": 0,
                    "data": {"code": 86090},
                })
            return _build_response(200, {
                "code": 0,
                "data": {"code": 0, "url": "https://passport.bilibili.com/callback?SESSDATA=abc"},
            })

        monkeypatch.setattr(mock_client, "get", fake_get)
        redirect = _poll_qr_login(mock_client, "key_123", poll_interval=0.01, timeout=10)
        assert redirect

    def test_expired(self, mock_client, monkeypatch):
        def fake_get(url, **kw):
            return _build_response(200, {
                "code": 0,
                "data": {"code": 86038},
            })
        monkeypatch.setattr(mock_client, "get", fake_get)

        with pytest.raises(TimeoutError, match="二维码已过期"):
            _poll_qr_login(mock_client, "key_123", poll_interval=0.01, timeout=10)

    def test_timeout(self, mock_client, monkeypatch):
        def fake_get(url, **kw):
            return _build_response(200, {
                "code": 0,
                "data": {"code": 86101},
            })
        monkeypatch.setattr(mock_client, "get", fake_get)

        with pytest.raises(TimeoutError, match="等待超时"):
            _poll_qr_login(mock_client, "key_123", poll_interval=0.01, timeout=0.1)


class TestCompleteLogin:
    def test_get_cookie_value(self):
        jar = httpx.Cookies()
        jar.set("SESSDATA", "abc123", domain=".bilibili.com")
        assert _get_cookie_value(jar, "SESSDATA") == "abc123"
        assert _get_cookie_value(jar, "nonexistent") is None


class TestValidateSession:
    def test_logged_in(self, monkeypatch):
        def fake_get(self, url, **kw):
            return _build_response(200, {
                "code": 0,
                "data": {"isLogin": True, "uname": "TestUser", "vip_status": 1},
            })

        monkeypatch.setattr(httpx.Client, "get", fake_get)
        info = validate_bilibili_session("abc", "def")
        assert info["is_login"] is True
        assert info["user_name"] == "TestUser"

    def test_not_logged_in(self, monkeypatch):
        def fake_get(self, url, **kw):
            return _build_response(200, {
                "code": 0,
                "data": {"isLogin": False},
            })

        monkeypatch.setattr(httpx.Client, "get", fake_get)
        info = validate_bilibili_session("invalid", None)
        assert info["is_login"] is False

    def test_no_sessdata(self):
        info = validate_bilibili_session(None, None)
        assert info["is_login"] is False
        assert info["user_name"] is None


class TestLoginBilibiliEndToEnd:
    def test_full_flow(self, monkeypatch):
        qr_calls = 0
        poll_calls = 0

        def fake_client_get(self, url, **kw):
            nonlocal qr_calls, poll_calls
            if "qrcode/generate" in str(url):
                qr_calls += 1
                return _build_response(200, {
                    "code": 0,
                    "data": {"url": "https://passport.bilibili.com/scan", "qrcode_key": "key_123"},
                })
            elif "qrcode/poll" in str(url):
                poll_calls += 1
                return _build_response(200, {
                    "code": 0,
                    "data": {"code": 0, "url": "https://passport.bilibili.com/callback?SESSDATA=abc&bili_jct=def"},
                })
            elif "web-interface/nav" in str(url):
                return _build_response(200, {
                    "code": 0,
                    "data": {"isLogin": True, "uname": "TestUser"},
                })
            else:
                # Redirect URL follow - set cookies directly on client's jar
                self.cookies.set("SESSDATA", "abc", domain=".bilibili.com")
                self.cookies.set("bili_jct", "def", domain=".bilibili.com")
                return _build_response(200, {"code": 0, "data": {}})

        monkeypatch.setattr(httpx.Client, "get", fake_client_get)
        # Prevent actual QR display
        monkeypatch.setattr("clipvault.login._show_qr_code", lambda url, mode: None)

        # Mock store_credential to avoid file I/O
        stored: dict = {}
        monkeypatch.setattr("clipvault.login.store_credential", lambda platform, **kw: stored.update(kw) or "/mock/path")

        result = login_bilibili(poll_interval=0.01, timeout=10)

        assert result["status"] == "ok"
        assert result["platform"] == "bilibili"
        assert result["is_login"] is True
        assert stored.get("sessdata") == "abc"
        assert stored.get("bili_jct") == "def"

    def test_no_credentials_extracted(self, monkeypatch):
        def fake_get(self, url, **kw):
            if "qrcode/poll" in str(url):
                return _build_response(200, {
                    "code": 0,
                    "data": {"code": 0, "url": "https://passport.bilibili.com/callback"},
                })
            return _build_response(200, {
                "code": 0,
                "data": {"url": "https://passport.bilibili.com/scan", "qrcode_key": "key_123"},
            })

        monkeypatch.setattr(httpx.Client, "get", fake_get)
        monkeypatch.setattr("clipvault.login._show_qr_code", lambda url, mode: None)

        with pytest.raises(RuntimeError, match="未能从登录响应中提取任何凭据"):
            login_bilibili(poll_interval=0.01, timeout=10)
