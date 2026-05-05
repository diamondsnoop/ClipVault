from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlatformAdapter:
    name: str
    domains: tuple[str, ...]
    languages: tuple[str, ...]

    def matches_url(self, url: str) -> bool:
        try:
            hostname = urllib.parse.urlparse(url).hostname
        except Exception:
            hostname = None
        if not hostname:
            return False
        return any(_domain_match(hostname, domain) for domain in self.domains)

    def flat_entry_url(self, entry: dict[str, Any], *, source_url: str) -> str | None:
        video_url = entry.get("webpage_url") or entry.get("url")
        if isinstance(video_url, str) and urllib.parse.urlparse(video_url).scheme:
            return video_url
        if isinstance(video_url, str) and video_url.strip():
            joined = urllib.parse.urljoin(source_url, video_url)
            if urllib.parse.urlparse(joined).scheme:
                return joined
        return None


class YouTubeAdapter(PlatformAdapter):
    def flat_entry_url(self, entry: dict[str, Any], *, source_url: str) -> str | None:
        raw_url = entry.get("webpage_url") or entry.get("url")
        if isinstance(raw_url, str) and urllib.parse.urlparse(raw_url).scheme:
            return raw_url
        if isinstance(raw_url, str) and raw_url.startswith("/"):
            video_url = super().flat_entry_url(entry, source_url=source_url)
            if video_url:
                return video_url
        if entry.get("ie_key") not in (None, "Youtube"):
            return super().flat_entry_url(entry, source_url=source_url)
        video_id = entry.get("id")
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        video_url = super().flat_entry_url(entry, source_url=source_url)
        if video_url:
            return video_url
        return None


class BilibiliAdapter(PlatformAdapter):
    def flat_entry_url(self, entry: dict[str, Any], *, source_url: str) -> str | None:
        video_url = entry.get("webpage_url") or entry.get("url")
        if isinstance(video_url, str) and urllib.parse.urlparse(video_url).scheme:
            return video_url
        candidate = str(entry.get("id") or video_url or "").strip()
        if candidate.startswith(("BV", "av")):
            return f"https://www.bilibili.com/video/{candidate}"
        return super().flat_entry_url(entry, source_url=source_url)


class DouyinAdapter(PlatformAdapter):
    def flat_entry_url(self, entry: dict[str, Any], *, source_url: str) -> str | None:
        video_url = entry.get("webpage_url") or entry.get("url")
        if isinstance(video_url, str) and urllib.parse.urlparse(video_url).scheme:
            return video_url
        candidate = str(entry.get("id") or video_url or "").strip()
        if candidate and not candidate.startswith("/"):
            return f"https://www.douyin.com/video/{candidate}"
        return super().flat_entry_url(entry, source_url=source_url)


def _domain_match(hostname: str, domain: str) -> bool:
    hostname = hostname.lower()
    domain = domain.lower()
    return hostname == domain or hostname.endswith("." + domain)


ADAPTERS: dict[str, PlatformAdapter] = {
    "bilibili": BilibiliAdapter(
        name="bilibili",
        domains=("bilibili.com", "b23.tv"),
        languages=("zh-CN", "zh-Hans", "zh-Hans-CN", "zh", "cmn-Hans-CN", "en"),
    ),
    "youtube": YouTubeAdapter(
        name="youtube",
        domains=("youtube.com", "youtu.be"),
        languages=("en", "zh-CN", "zh-Hans", "zh"),
    ),
    "douyin": DouyinAdapter(
        name="douyin",
        domains=("douyin.com",),
        languages=("zh-CN", "zh-Hans", "zh"),
    ),
}


PLATFORMS: dict[str, dict[str, tuple[str, ...]]] = {
    name: {"domains": adapter.domains, "languages": adapter.languages}
    for name, adapter in ADAPTERS.items()
}


def identify_platform(url: str) -> str:
    for adapter in ADAPTERS.values():
        if adapter.matches_url(url):
            return adapter.name
    return "unknown"


def platform_languages(platform: str) -> tuple[str, ...]:
    adapter = ADAPTERS.get(platform)
    return adapter.languages if adapter else ("en",)


def adapter_for_url(url: str) -> PlatformAdapter | None:
    platform = identify_platform(url)
    return ADAPTERS.get(platform)
