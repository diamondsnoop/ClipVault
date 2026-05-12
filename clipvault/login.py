from __future__ import annotations

import sys
import time
import urllib.parse
from typing import Any

import httpx

from .auth import clear_cookie_cache
from .credentials import PLATFORM_CREDENTIAL_KEYS, remove_credential, store_credential
from .runtime_logs import emit_log

QR_GENERATE_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
USER_INFO_API = "https://api.bilibili.com/x/web-interface/nav"

QR_STATUS_NOT_SCANNED = 86101
QR_STATUS_SCANNED = 86090
QR_STATUS_CONFIRMED = 0
QR_STATUS_EXPIRED = 86038

_BILIBILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}


def login_bilibili(
    mode: str = "terminal",
    poll_interval: float = 2.0,
    timeout: int = 180,
) -> dict[str, Any]:
    """Full Bilibili QR code login flow.

    Returns the stored credential record on success.
    """
    client = httpx.Client(follow_redirects=True, headers=_BILIBILI_HEADERS.copy())

    # Step 1: generate QR code
    qr_url, qrcode_key = _generate_qr_login(client)

    # Step 2: display QR code
    _show_qr_code(qr_url, mode=mode)

    # Step 3: poll for scan/confirm
    redirect_url = _poll_qr_login(client, qrcode_key, poll_interval=poll_interval, timeout=timeout)

    # Step 4: complete login - follow redirect to capture cookies
    sessdata, bili_jct = _complete_login(client, redirect_url)

    # Step 5: save credentials
    creds: dict[str, str] = {}
    if sessdata:
        creds["sessdata"] = sessdata
    if bili_jct:
        creds["bili_jct"] = bili_jct
    if not creds:
        raise RuntimeError("未能从登录响应中提取任何凭据。")
    path = store_credential("bilibili", **creds)
    emit_log("auth", f"凭据已保存到：{path}", level="success")

    # Step 6: validate session
    info = validate_bilibili_session(sessdata, bili_jct)
    if info.get("is_login"):
        emit_log("auth", f"已登录账号：{info.get('user_name', '未知用户')}", level="success")
    else:
        raw = info.get("_raw_response")
        emit_log(
            "auth",
            "凭据已保存，但会话校验失败。"
            f"API 返回：isLogin={raw.get('isLogin') if raw else 'N/A'}，"
            f"uname={info.get('user_name')}",
            level="warning",
        )

    return {
        "status": "ok",
        "platform": "bilibili",
        "user_name": info.get("user_name"),
        "is_login": info.get("is_login", False),
    }


def _generate_qr_login(client: httpx.Client) -> tuple[str, str]:
    """Call QR generate API and return (qr_url, qrcode_key)."""
    resp = client.get(QR_GENERATE_API, params={"source": "main-fe-header"})
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"二维码生成接口返回错误：{data}")
    url = data.get("data", {}).get("url")
    key = data.get("data", {}).get("qrcode_key")
    if not url or not key:
        raise RuntimeError(f"二维码生成响应缺少 url 或 qrcode_key：{data}")
    return url, key


def _show_qr_code(url: str, mode: str = "terminal") -> None:
    """Render QR code in terminal or browser."""
    import segno

    qr = segno.make_qr(url)
    if mode == "web":
        try:
            qr.show()
            return
        except Exception:
            emit_log("auth", "浏览器二维码展示失败，回退到终端输出", level="warning")

    # Terminal mode: render as block characters
    emit_log("auth", "请使用哔哩哔哩 App 扫描下方二维码登录")
    qr.terminal(out=sys.stderr, compact=True)
    print(file=sys.stderr)


def _poll_qr_login(
    client: httpx.Client,
    qrcode_key: str,
    poll_interval: float = 2.0,
    timeout: int = 180,
) -> str:
    """Poll QR login status until confirmed or expired. Returns redirect URL on success."""
    deadline = time.monotonic() + timeout
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("二维码登录等待超时，请重试。")

        resp = client.get(QR_POLL_API, params={"qrcode_key": qrcode_key, "source": "main-fe-header"})
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", {})
        status = data.get("code")

        if status == QR_STATUS_NOT_SCANNED:
            emit_log("auth", "等待扫码中…")
        elif status == QR_STATUS_SCANNED:
            emit_log("auth", "已扫码，等待手机确认…")
        elif status == QR_STATUS_CONFIRMED:
            redirect_url = data.get("url", "")
            if not redirect_url:
                raise RuntimeError("登录已确认，但没有收到跳转 URL。")
            return redirect_url
        elif status == QR_STATUS_EXPIRED:
            raise TimeoutError(
                "二维码已过期，请重新运行 `clipvault auth login` 获取新的二维码。"
            )
        else:
            emit_log("auth", f"收到未知二维码状态：{status}", level="warning")

        time.sleep(poll_interval)


def _complete_login(client: httpx.Client, redirect_url: str) -> tuple[str | None, str | None]:
    """Follow the redirect URL to capture Set-Cookie headers.

    Returns (sessdata, bili_jct).
    """
    # Follow redirect so httpx cookie jar captures Set-Cookie headers
    try:
        resp = client.get(redirect_url)
        resp.raise_for_status()
    except httpx.HTTPError:
        pass  # Cookie jar may still have partial data

    # Extract from cookie jar (preferred)
    sessdata = _get_cookie_value(client.cookies, "SESSDATA")
    bili_jct = _get_cookie_value(client.cookies, "bili_jct")

    # Fallback: parse from redirect URL query params
    if not sessdata or not bili_jct:
        parsed = urllib.parse.urlparse(redirect_url)
        qs = urllib.parse.parse_qs(parsed.query)
        if not sessdata:
            sessdata = qs.get("SESSDATA", [None])[0]
        if not bili_jct:
            bili_jct = qs.get("bili_jct", [None])[0]

    # Normalize using quote(unquote(...)) like yutto — ensures commas and
    # other special chars are consistently encoded for Bilibili's API.
    if sessdata:
        sessdata = urllib.parse.quote(urllib.parse.unquote(sessdata))
    if bili_jct:
        bili_jct = urllib.parse.quote(urllib.parse.unquote(bili_jct))

    return sessdata, bili_jct


def _get_cookie_value(cookies: httpx.Cookies, name: str) -> str | None:
    """Get a cookie value by name, preferring .bilibili.com domain."""
    import httpx as _httpx

    try:
        return cookies.get(name, domain=".bilibili.com")
    except _httpx.CookieConflict:
        # Multiple cookies with same name on different domains - try each
        for domain in (".bilibili.com", "bilibili.com", ".passport.bilibili.com", "passport.bilibili.com"):
            try:
                val = cookies.get(name, domain=domain)
                if val:
                    return val
            except _httpx.CookieConflict:
                continue
    return None


def validate_bilibili_session(sessdata: str | None, bili_jct: str | None) -> dict[str, Any]:
    """Check if the current Bilibili session is valid.

    Returns user info dict with at least 'is_login' and 'user_name' keys.
    """
    if not sessdata:
        return {"is_login": False, "user_name": None}

    jar = httpx.Cookies()
    # Don't restrict domain — httpx will match the request URL automatically
    jar.set("SESSDATA", sessdata)
    if bili_jct:
        jar.set("bili_jct", bili_jct)

    client = httpx.Client(cookies=jar, follow_redirects=True, headers=_BILIBILI_HEADERS.copy())
    try:
        resp = client.get(USER_INFO_API)
        resp.raise_for_status()
        data = resp.json()
        nav_data = data.get("data", {})
        return {
            "is_login": nav_data.get("isLogin", False),
            "user_name": nav_data.get("uname"),
            "vip_status": nav_data.get("vip_status"),
            "_raw_response": nav_data,
        }
    except (httpx.HTTPError, ValueError) as exc:
        emit_log("auth", f"会话校验请求失败：{exc}", level="warning")
        return {"is_login": False, "user_name": None, "error": str(exc), "_raw_response": None}


def logout_bilibili() -> dict[str, Any]:
    """Remove Bilibili credentials and clear cached cookie file."""
    removed = remove_credential("bilibili")
    if not removed:
        return {"status": "error", "message": "未找到哔哩哔哩已保存凭据。"}
    clear_cookie_cache()
    return {"status": "ok", "platform": "bilibili"}
