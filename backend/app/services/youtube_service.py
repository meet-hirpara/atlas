"""YouTube search — Data API v3 with DuckDuckGo site:youtube.com fallback."""

from __future__ import annotations

import json
import re
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import get_settings

settings = get_settings()

YOUTUBE_MARKER = "<!--nexus-youtube:"
YOUTUBE_MARKER_END = "-->"

_VIDEO_INTENT_RE = re.compile(
    r"\b("
    r"youtube|youtu\.be|"
    r"video(?:s)?|tutorial(?:s)?|walkthrough|"
    r"watch|show\s+me\s+(?:a\s+)?video|"
    r"recommend(?:ation)?s?\s+(?:for\s+)?video|"
    r"video\s+(?:on|about|for|tutorial)|"
    r"how\s+to\s+.+\s+(?:video|tutorial)|"
    r"learn\s+.+\s+(?:video|youtube)"
    r")\b",
    re.I,
)

_YT_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
    re.I,
)


def detect_video_intent(message: str) -> bool:
    text = (message or "").strip()
    if len(text) < 6:
        return False
    if _VIDEO_INTENT_RE.search(text):
        return True
    if _YT_URL_RE.search(text):
        return True
    return False


def _extract_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    match = _YT_URL_RE.search(url)
    if match:
        return match.group(1)
    try:
        parsed = urlparse(url)
        if "youtube.com" in parsed.netloc:
            qs = parse_qs(parsed.query)
            vid = qs.get("v", [None])[0]
            if vid and len(vid) == 11:
                return vid
    except Exception:
        pass
    return None


def _normalize_video(item: dict) -> Optional[dict]:
    video_id = item.get("videoId") or _extract_video_id(item.get("url", ""))
    if not video_id:
        return None
    title = (item.get("title") or "YouTube video").strip()
    channel = (item.get("channel") or "").strip()
    thumbnail = (item.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg").strip()
    url = (item.get("url") or f"https://www.youtube.com/watch?v={video_id}").strip()
    description = (item.get("description") or "").strip()[:240]
    return {
        "videoId": video_id,
        "title": title[:140],
        "channel": channel[:80],
        "thumbnail": thumbnail,
        "url": url,
        "description": description,
    }


def _search_youtube_api(query: str, max_results: int = 5) -> List[dict]:
    params = {
        "part": "snippet",
        "type": "video",
        "q": query.strip(),
        "maxResults": max(1, min(max_results, 10)),
        "key": settings.youtube_api_key,
        "safeSearch": "moderate",
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.get("https://www.googleapis.com/youtube/v3/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    videos: List[dict] = []
    for item in data.get("items", []):
        vid = item.get("id", {}).get("videoId")
        snippet = item.get("snippet") or {}
        thumbs = snippet.get("thumbnails") or {}
        thumb = (
            (thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}).get("url", "")
        )
        normalized = _normalize_video({
            "videoId": vid,
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "thumbnail": thumb,
            "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
            "description": snippet.get("description", ""),
        })
        if normalized:
            videos.append(normalized)
        if len(videos) >= max_results:
            break
    return videos


def _search_youtube_ddg(query: str, max_results: int = 5) -> List[dict]:
    results: List[dict] = []
    search_query = f"site:youtube.com {query.strip()}"
    last_error: Optional[Exception] = None

    for factory in (
        lambda: __import__("duckduckgo_search", fromlist=["DDGS"]).DDGS,
        lambda: __import__("ddgs", fromlist=["DDGS"]).DDGS,
    ):
        try:
            DDGS = factory()
            with DDGS() as ddgs:
                for item in ddgs.text(search_query, max_results=max_results + 8):
                    url = item.get("href", item.get("link", ""))
                    video_id = _extract_video_id(url)
                    if not video_id:
                        continue
                    normalized = _normalize_video({
                        "videoId": video_id,
                        "title": item.get("title", ""),
                        "channel": "",
                        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                        "url": url or f"https://www.youtube.com/watch?v={video_id}",
                        "description": item.get("body", item.get("snippet", "")),
                    })
                    if normalized:
                        results.append(normalized)
                    if len(results) >= max_results:
                        return results
            if results:
                return results
        except Exception as e:
            last_error = e
            results = []

    if last_error and not results:
        raise RuntimeError(f"YouTube DuckDuckGo search failed: {last_error}") from last_error
    return results


def search_youtube(query: str, max_results: int = 5) -> List[dict]:
    query = query.strip()
    if not query:
        return []

    max_results = max(3, min(max_results, 5))
    seen: set[str] = set()
    videos: List[dict] = []

    if settings.youtube_api_key:
        try:
            for v in _search_youtube_api(query, max_results):
                if v["videoId"] not in seen:
                    seen.add(v["videoId"])
                    videos.append(v)
        except Exception:
            pass

    if len(videos) < max_results:
        try:
            for v in _search_youtube_ddg(query, max_results):
                if v["videoId"] not in seen:
                    seen.add(v["videoId"])
                    videos.append(v)
                if len(videos) >= max_results:
                    break
        except Exception:
            pass

    return videos[:max_results]


def encode_youtube_message(content: str, videos: List[dict]) -> str:
    if not videos:
        return content
    payload = json.dumps(videos, ensure_ascii=False)
    return f"{content.rstrip()}\n{YOUTUBE_MARKER}{payload}{YOUTUBE_MARKER_END}"


def youtube_event(videos: List[dict]) -> str:
    return f"data: {json.dumps({'youtube_videos': videos})}\n\n"
