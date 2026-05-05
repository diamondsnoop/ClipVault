from __future__ import annotations

from pathlib import Path

from clipvault.platforms import PLATFORMS, _flat_entry_url, identify_platform, platform_languages


# ── identify_platform ──────────────────────────────────────────────────


def test_identify_bilibili():
    assert identify_platform("https://www.bilibili.com/video/BV1xx") == "bilibili"
    assert identify_platform("https://b23.tv/abc123") == "bilibili"
    assert identify_platform("https://www.bilibili.com/read/cv123") == "bilibili"
    assert identify_platform("https://space.bilibili.com/123456/video") == "bilibili"
    assert identify_platform("https://www.bilibili.com/list/123456") == "bilibili"
    assert identify_platform("https://bilibili.com/video/BV1xx") == "bilibili"


def test_identify_youtube():
    assert identify_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert identify_platform("https://youtu.be/dQw4w9WgXcQ") == "youtube"
    assert identify_platform("https://m.youtube.com/watch?v=abc") == "youtube"
    assert identify_platform("https://music.youtube.com/watch?v=abc") == "youtube"
    assert identify_platform("https://youtube.com/watch?v=abc") == "youtube"


def test_identify_douyin():
    assert identify_platform("https://www.douyin.com/video/123") == "douyin"
    assert identify_platform("https://douyin.com/abc") == "douyin"


def test_identify_fake_domains_not_matched():
    """Substring-in-hostname must NOT cause false positives."""
    assert identify_platform("https://notyoutube.com/watch?v=x") == "unknown"
    assert identify_platform("https://youtube.com.evil.test/watch?v=x") == "unknown"
    assert identify_platform("https://evilbilibili.com/video/BV1") == "unknown"
    assert identify_platform("https://www.douyin.com.evil.test/video/1") == "unknown"


def test_identify_unknown():
    assert identify_platform("https://vimeo.com/12345") == "unknown"
    assert identify_platform("https://example.com/video") == "unknown"
    assert identify_platform("https://twitter.com/user/status/123") == "unknown"


def test_identify_case_insensitive():
    assert identify_platform("https://www.BILIBILI.com/video/BV1xx") == "bilibili"
    assert identify_platform("https://www.YOUTUBE.com/watch?v=abc") == "youtube"


def test_identify_edge_empty():
    assert identify_platform("") == "unknown"
    assert identify_platform("not-a-url") == "unknown"
    assert identify_platform("http://") == "unknown"
    assert identify_platform("   ") == "unknown"


# ── platform_languages ─────────────────────────────────────────────────


def test_languages_bilibili():
    langs = platform_languages("bilibili")
    assert langs[0] == "zh-CN"
    assert "en" in langs


def test_languages_youtube():
    langs = platform_languages("youtube")
    assert langs[0] == "en"
    assert "zh-CN" in langs


def test_languages_unknown():
    # Unknown platforms fall back to English-only
    langs = platform_languages("unknown")
    assert langs == ("en",)


def test_languages_unregistered():
    langs = platform_languages("nonexistent")
    assert langs == ("en",)


# ── flat playlist entries ─────────────────────────────────────────────


def test_flat_entry_url_prefers_webpage_url():
    assert _flat_entry_url(
        {"webpage_url": "https://example.com/v", "url": "abc"},
        source_url="https://www.youtube.com/@x",
    ) == "https://example.com/v"


def test_flat_entry_url_builds_youtube_url_from_id():
    assert _flat_entry_url(
        {"ie_key": "Youtube", "id": "abc", "url": "abc"},
        source_url="https://www.youtube.com/@x",
    ) == "https://www.youtube.com/watch?v=abc"


def test_flat_entry_url_builds_bilibili_url_from_bv_id():
    assert _flat_entry_url(
        {"id": "BV123", "url": "BV123"},
        source_url="https://space.bilibili.com/123/video",
    ) == "https://www.bilibili.com/video/BV123"


def test_flat_entry_url_builds_bilibili_url_from_av_id():
    assert _flat_entry_url(
        {"id": "av987", "url": "av987"},
        source_url="https://space.bilibili.com/123/video",
    ) == "https://www.bilibili.com/video/av987"


def test_flat_entry_url_builds_douyin_url_from_id():
    assert _flat_entry_url(
        {"id": "712345", "url": "712345"},
        source_url="https://www.douyin.com/user/example",
    ) == "https://www.douyin.com/video/712345"


def test_flat_entry_url_joins_relative_path():
    assert _flat_entry_url(
        {"url": "/video/BV123"},
        source_url="https://www.bilibili.com/account/history",
    ) == "https://www.bilibili.com/video/BV123"


# ── PLATFORMS registry shape ──────────────────────────────────────────


def test_every_platform_has_domains():
    for name, config in PLATFORMS.items():
        assert config.get("domains"), f"{name} missing domains"
        assert isinstance(config["domains"], tuple)


def test_every_platform_has_languages():
    for name, config in PLATFORMS.items():
        assert config.get("languages"), f"{name} missing languages"
        assert isinstance(config["languages"], tuple)


# ── Authenticated yt-dlp access ───────────────────────────────────────


def test_extract_info_passes_cookies_to_ytdlp(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("clipvault.auth._cached_clipvault_cookie_path", None)
    monkeypatch.setattr("clipvault.credentials.get_config_dir", lambda: tmp_path)
    auth_toml = tmp_path / "auth.toml"
    auth_toml.write_text('[bilibili]\nsessdata = "abc"\n', encoding="utf-8")

    captured: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, opts):
            captured.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download):
            assert url == "https://www.bilibili.com/video/BV1xx"
            assert download is False
            return {"title": "T", "uploader": "U"}

    monkeypatch.setattr("clipvault.platforms.YoutubeDL", FakeYoutubeDL)

    from clipvault.platforms import extract_info

    result = extract_info("https://www.bilibili.com/video/BV1xx", verbose=False, cookies=True)

    assert result["title"] == "T"
    assert isinstance(captured["cookiefile"], str)
    assert Path(captured["cookiefile"]).is_file()
