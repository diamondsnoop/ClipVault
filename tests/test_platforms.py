from __future__ import annotations

from clipvault.platforms import PLATFORMS, identify_platform, platform_languages


# ── identify_platform ──────────────────────────────────────────────────


def test_identify_bilibili():
    assert identify_platform("https://www.bilibili.com/video/BV1xx") == "bilibili"
    assert identify_platform("https://b23.tv/abc123") == "bilibili"
    assert identify_platform("https://www.bilibili.com/read/cv123") == "bilibili"
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


# ── PLATFORMS registry shape ──────────────────────────────────────────


def test_every_platform_has_domains():
    for name, config in PLATFORMS.items():
        assert config.get("domains"), f"{name} missing domains"
        assert isinstance(config["domains"], tuple)


def test_every_platform_has_languages():
    for name, config in PLATFORMS.items():
        assert config.get("languages"), f"{name} missing languages"
        assert isinstance(config["languages"], tuple)
