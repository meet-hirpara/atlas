from typing import List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.models.bot_settings import BotSettings
from app.services.web_search_service import (
    format_results_for_llm,
    get_active_provider,
    merge_sources,
    needs_web_search,
    results_to_sources,
    search_web,
)


class WebSearchInput(BaseModel):
    query: str = Field(description="Specific search query — be precise for best results")
    max_results: int = Field(default=5, description="Number of results (1-8)")


class WebNewsInput(BaseModel):
    query: str = Field(description="News topic or event to search")
    max_results: int = Field(default=5, description="Number of articles (1-8)")


def _search_news(
    query: str,
    max_results: int = 5,
    sources_collector: Optional[list] = None,
) -> str:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "News search unavailable — install duckduckgo-search"

    max_results = max(1, min(max_results, 8))
    items = []
    with DDGS() as ddgs:
        for item in ddgs.news(query, max_results=max_results):
            items.append({
                "title": item.get("title", ""),
                "url": item.get("url", item.get("link", "")),
                "snippet": item.get("body", item.get("excerpt", "")),
                "source": "duckduckgo_news",
                "score": 0.5,
            })
    from app.services.web_search_service import _filter_results
    filtered = _filter_results(items, max_results)
    start_index = len(sources_collector) + 1 if sources_collector is not None else 1
    if sources_collector is not None:
        merge_sources(sources_collector, results_to_sources(filtered))
    return format_results_for_llm(filtered, query, "duckduckgo_news", start_index=start_index)


def build_web_search_tools(
    bot_settings: Optional[BotSettings] = None,
    user_message: str = "",
    sources_collector: Optional[list] = None,
) -> List[StructuredTool]:
    mode = bot_settings.web_search_mode if bot_settings else "auto"
    if mode == "off":
        return []
    # Attach tools only when the message looks like it needs search.
    # Mode "on" still prefetches via should_prefetch_web; forcing tools on every
    # turn would push chat into the non-streaming run_with_tools path.
    if not needs_web_search(user_message):
        return []

    provider = get_active_provider()

    def _internet_search(query: str, max_results: int = 5) -> str:
        max_results = max(1, min(max_results, 8))
        results, used = search_web(query, max_results)
        start_index = len(sources_collector) + 1 if sources_collector is not None else 1
        if sources_collector is not None:
            merge_sources(sources_collector, results_to_sources(results))
        return format_results_for_llm(results, query, used, start_index=start_index)

    tools = [
        StructuredTool.from_function(
            func=_internet_search,
            name="internet_search",
            description=(
                f"Search the live internet for current, factual information ({provider}). "
                "Use for news, prices, recent events, documentation, or anything not in your training data. "
                "Returns curated snippets with source URLs."
            ),
            args_schema=WebSearchInput,
        ),
        StructuredTool.from_function(
            func=lambda query, max_results=5: _search_news(query, max_results, sources_collector),
            name="internet_news_search",
            description="Search recent news articles on a topic. Use for breaking news and current events.",
            args_schema=WebNewsInput,
        ),
    ]
    return tools


def build_web_search_prompt() -> str:
    provider = get_active_provider()
    return f"""
## Internet search (enabled)
You have live web access via `{provider}`-powered search tools.
- Use `internet_search` when the user asks about current events, real-time data, or facts you're unsure about.
- Use `internet_news_search` for breaking news and recent headlines.
- Always cite facts inline as [1], [2], etc. matching the numbered sources in search results.
- Do not invent facts — if search returns nothing, say so.
"""

def should_prefetch_web(bot_settings: Optional[BotSettings], message: str) -> bool:
    if not bot_settings or bot_settings.web_search_mode == "off":
        return False
    # "on" = always prefetch live context (tools still only attach when needed)
    if bot_settings.web_search_mode == "on":
        return len(message.strip()) >= 8
    return needs_web_search(message)
