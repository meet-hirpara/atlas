"""Web search — Tavily (AI-grade) with DuckDuckGo free fallback."""

from __future__ import annotations

import json
import re
from typing import List, Optional
from urllib.parse import urlparse

SOURCES_MARKER = "<!--nexus-sources:"
SOURCES_MARKER_END = "-->"

import httpx

from app.config import get_settings

settings = get_settings()

BLOCKED_DOMAINS = {
    "pinterest.com", "facebook.com", "instagram.com", "tiktok.com",
    "quora.com", "answers.yahoo.com",
}

WEB_QUERY_PATTERNS = re.compile(
    r"\b("
    r"today|tonight|yesterday|this week|this month|202[4-9]|203\d|"
    r"latest|current|recent|news|price|stock|weather|score|"
    r"who is|what is|when did|where is|how much|how many|"
    r"search|look up|find out|on the internet|online|"
    r"release date|announced|election|ceo of|president of"
    r")\b",
    re.I,
)


def get_active_provider() -> str:
    if settings.tavily_api_key:
        return "tavily"
    return "duckduckgo"


def needs_web_search(message: str) -> bool:
    if len(message.strip()) < 8:
        return False
    if WEB_QUERY_PATTERNS.search(message):
        return True
    if "?" in message and len(message) > 20:
        return True
    return False


def _is_quality_domain(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return host not in BLOCKED_DOMAINS
    except Exception:
        return True


def _filter_results(results: List[dict], max_results: int = 6, min_snippet: int = 30) -> List[dict]:
    seen_urls = set()
    filtered = []
    for r in results:
        url = r.get("url", "")
        if url and url in seen_urls:
            continue
        if url and not _is_quality_domain(url):
            continue
        snippet = (r.get("snippet") or r.get("content") or "").strip()
        title = (r.get("title") or "").strip()
        if not url and not snippet and not title:
            continue
        if min_snippet > 0 and len(snippet) < min_snippet and not title:
            continue
        if url:
            seen_urls.add(url)
        filtered.append(r)
        if len(filtered) >= max_results:
            break
    return filtered


def _search_tavily(query: str, max_results: int = 6) -> List[dict]:
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results + 2,
        "include_answer": True,
        "include_raw_content": False,
    }
    with httpx.Client(timeout=25.0) as client:
        resp = client.post("https://api.tavily.com/search", json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = []
    answer = data.get("answer")
    if answer:
        results.append({
            "title": "Tavily AI summary",
            "url": "",
            "snippet": answer,
            "source": "tavily",
            "score": 1.0,
        })
    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", item.get("snippet", ""))[:2500],
            "source": "tavily",
            "score": item.get("score", 0.5),
        })
    return _filter_results(results, max_results)


def _search_duckduckgo(query: str, max_results: int = 6, min_snippet: int = 30) -> List[dict]:
    results = []
    last_error: Optional[Exception] = None

    for factory in (
        lambda: __import__("duckduckgo_search", fromlist=["DDGS"]).DDGS,
        lambda: __import__("ddgs", fromlist=["DDGS"]).DDGS,
    ):
        try:
            DDGS = factory()
            with DDGS() as ddgs:
                for item in ddgs.text(query, max_results=max_results + 6):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("href", item.get("link", "")),
                        "snippet": item.get("body", item.get("snippet", "")),
                        "source": "duckduckgo",
                        "score": 0.5,
                    })
            if results:
                return _filter_results(results, max_results, min_snippet=min_snippet)
        except Exception as e:
            last_error = e
            results = []

    if last_error:
        raise RuntimeError(f"DuckDuckGo search failed: {last_error}") from last_error
    return []


def search_news(query: str, max_results: int = 5) -> List[dict]:
    """Recent news articles for deep research."""
    max_results = max(1, min(max_results, 8))
    items: List[dict] = []
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        try:
            from ddgs import DDGS
        except ImportError:
            return []

    try:
        with DDGS() as ddgs:
            for item in ddgs.news(query, max_results=max_results + 3):
                items.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", item.get("link", "")),
                    "snippet": item.get("body", item.get("excerpt", "")),
                    "source": "duckduckgo_news",
                    "score": 0.65,
                })
    except Exception:
        return []
    return _filter_results(items, max_results, min_snippet=0)


def search_web(query: str, max_results: int = 6) -> tuple[List[dict], str]:
    """Returns (results, provider_name)."""
    query = query.strip()
    if not query:
        return [], get_active_provider()

    if settings.tavily_api_key:
        try:
            return _search_tavily(query, max_results), "tavily"
        except Exception:
            pass

    try:
        return _search_duckduckgo(query, max_results), "duckduckgo"
    except Exception as e:
        raise RuntimeError(f"Web search failed: {e}") from e


def search_web_deep(query: str, max_results: int = 8) -> tuple[List[dict], str]:
    """Relaxed filtering for deep research — keeps more snippets."""
    query = query.strip()
    if not query:
        return [], get_active_provider()

    if settings.tavily_api_key:
        try:
            return _search_tavily(query, max_results + 2), "tavily"
        except Exception:
            pass

    try:
        return _search_duckduckgo(query, max_results, min_snippet=8), "duckduckgo"
    except Exception as e:
        raise RuntimeError(f"Web search failed: {e}") from e


def results_to_sources(results: List[dict]) -> List[dict]:
    sources: List[dict] = []
    for i, r in enumerate(results, 1):
        url = (r.get("url") or "").strip()
        title = (r.get("title") or url or "Source").strip()
        snippet = (r.get("snippet") or "").strip()[:300]
        domain = ""
        if url:
            try:
                domain = urlparse(url).netloc.lower().replace("www.", "")
            except Exception:
                domain = ""
        sources.append({
            "id": i,
            "title": title[:120],
            "url": url,
            "snippet": snippet,
            "domain": domain,
        })
    return sources


def merge_sources(collector: List[dict], new_sources: List[dict]) -> None:
    seen = {s.get("url") or s.get("title") for s in collector if s.get("url") or s.get("title")}
    for source in new_sources:
        key = source.get("url") or source.get("title")
        if key and key in seen:
            continue
        entry = dict(source)
        entry["id"] = len(collector) + 1
        collector.append(entry)
        if key:
            seen.add(key)


def encode_sources_message(content: str, sources: List[dict]) -> str:
    if not sources:
        return content
    payload = json.dumps(sources, ensure_ascii=False)
    return f"{content.rstrip()}\n{SOURCES_MARKER}{payload}{SOURCES_MARKER_END}"


def format_results_for_llm(
    results: List[dict],
    query: str,
    provider: str,
    start_index: int = 1,
) -> str:
    if not results:
        return f"## Web search\nNo reliable results found for: {query}"

    lines = [
        f"## Web search results (provider: {provider})",
        f"Query: {query}",
        "Use these sources to answer accurately. Cite facts inline as [1], [2], etc. matching the source numbers below.",
        "",
    ]
    for i, r in enumerate(results, start_index):
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        snippet = (r.get("snippet") or "").strip()[:2500]
        header = f"### [{i}] {title}"
        if url:
            header += f"\nSource: {url}"
        lines.append(f"{header}\n{snippet}\n")
    return "\n".join(lines)


def search_and_format(query: str, max_results: int = 6) -> tuple[str, str, int, List[dict]]:
    """Returns (formatted_context, provider, result_count, sources)."""
    results, provider = search_web(query, max_results)
    sources = results_to_sources(results)
    return format_results_for_llm(results, query, provider), provider, len(results), sources
