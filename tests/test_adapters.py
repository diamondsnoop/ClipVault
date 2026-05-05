from __future__ import annotations

from clipvault.adapters import ADAPTERS, adapter_for_url, identify_platform, platform_languages


def test_adapter_for_url_known_platforms():
    assert adapter_for_url("https://www.bilibili.com/video/BV1") is ADAPTERS["bilibili"]
    assert adapter_for_url("https://www.youtube.com/watch?v=x") is ADAPTERS["youtube"]
    assert adapter_for_url("https://www.douyin.com/video/1") is ADAPTERS["douyin"]


def test_adapter_for_url_unknown():
    assert adapter_for_url("https://example.com/video/1") is None


def test_identify_platform_rejects_fake_domains():
    assert identify_platform("https://youtube.com.evil.test/watch?v=x") == "unknown"
    assert identify_platform("https://evilbilibili.com/video/BV1") == "unknown"


def test_platform_languages_fallback():
    assert platform_languages("unknown") == ("en",)


def test_bilibili_adapter_completes_bv_url():
    adapter = ADAPTERS["bilibili"]
    assert adapter.flat_entry_url(
        {"id": "BV123", "url": "BV123"},
        source_url="https://space.bilibili.com/123/video",
    ) == "https://www.bilibili.com/video/BV123"


def test_youtube_adapter_completes_id_url():
    adapter = ADAPTERS["youtube"]
    assert adapter.flat_entry_url(
        {"id": "abc", "url": "abc"},
        source_url="https://www.youtube.com/@Jabzy",
    ) == "https://www.youtube.com/watch?v=abc"


def test_douyin_adapter_completes_id_url():
    adapter = ADAPTERS["douyin"]
    assert adapter.flat_entry_url(
        {"id": "12345", "url": "12345"},
        source_url="https://www.douyin.com/user/test",
    ) == "https://www.douyin.com/video/12345"
