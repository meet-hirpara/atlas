"""Deep research — real multi-step web investigation (Gemini / ChatGPT style)."""

from __future__ import annotations

import asyncio
import json
import random
import re
from typing import AsyncGenerator, List, Optional, Set
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage, SystemMessage

from app.models.bot_settings import BotSettings
from app.services.llm_service import (
    RESEARCH_EXPAND_MAX_TOKENS,
    RESEARCH_MAX_TOKENS,
    RESEARCH_OUTLINE_MAX_TOKENS,
    get_llm,
)
from app.services.model_service import fetch_mistral_models, get_model_by_category, pick_specialist
from app.services.web_search_service import (
    format_results_for_llm,
    get_active_provider,
    search_news,
    search_web_deep,
)

PLANNING_TICKS = [
    ("Thinking", "Understanding your question…"),
    ("Thinking", "Breaking it into research angles…"),
    ("Thinking", "Identifying what to look up…"),
    ("Thinking", "Mapping key topics to explore…"),
]

ANALYZING_TICKS = [
    ("Analyzing", "Cross-referencing sources…"),
    ("Analyzing", "Checking facts across pages…"),
    ("Analyzing", "Ranking source quality…"),
    ("Analyzing", "Identifying gaps in coverage…"),
]

WRITING_TICKS = [
    ("Writing", "Building detailed outline…"),
    ("Writing", "Structuring 8–12 major sections…"),
    ("Writing", "Expanding sections in depth…"),
    ("Writing", "Synthesizing all sources…"),
    ("Writing", "Drafting your deep research report…"),
]

SEARCH_START = [
    "Querying the web…",
    "Looking this up online…",
    "Scanning search results…",
]

MIN_SOURCES = 3
PLANNED_QUERY_COUNT = 8
SEARCH_MAX_RESULTS = 10
MAX_MERGED_SOURCES = 32
MAX_CITATION_SOURCES = 28
RESEARCH_WRITER_TEMPERATURE = 0.6
RESEARCH_OUTLINE_TEMPERATURE = 0.4
MIN_BROAD_REPORT_WORDS = 3500
MIN_NARROW_REPORT_WORDS = 2200
MAX_EXPANSION_PASSES = 2


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _major_section_count(text: str) -> int:
    return len(re.findall(r"^##\s+", text or "", re.MULTILINE))


def _report_word_target(topic: str) -> int:
    """Heuristic: broad multi-faceted topics need longer reports."""
    broad_signals = re.compile(
        r"\b(compare|versus|vs\.?|history of|overview|landscape|impact|future|"
        r"regulation|market|industry|global|comprehensive|analyze|analysis)\b",
        re.I,
    )
    return MIN_BROAD_REPORT_WORDS if broad_signals.search(topic) else MIN_NARROW_REPORT_WORDS


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _source_card(result: dict) -> dict:
    url = (result.get("url") or "").strip()
    title = (result.get("title") or url or "Source").strip()
    domain = ""
    if url:
        try:
            domain = urlparse(url).netloc.lower().replace("www.", "")
        except Exception:
            domain = ""
    return {"title": title[:120], "url": url, "domain": domain}


def _research_event(
    phase: str,
    message: str,
    step: int = 0,
    total: int = 0,
    query: str = "",
    label: str = "",
    sources_found: int = 0,
    new_sources: Optional[List[dict]] = None,
) -> str:
    payload = {
        "phase": phase,
        "message": message,
        "step": step,
        "total": total,
        "query": query,
        "sources_found": sources_found,
    }
    if label:
        payload["label"] = label
    if new_sources:
        payload["new_sources"] = new_sources
    return _sse({"research": payload})


async def _tick_while_waiting(
    task: asyncio.Task,
    phase: str,
    ticks: List[tuple[str, str]],
    step: int,
    total: int,
) -> AsyncGenerator[str, None]:
    idx = 0
    while not task.done():
        tick_label, tick_msg = ticks[idx % len(ticks)]
        yield _research_event(phase, tick_msg, step, total, label=tick_label)
        idx += 1
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=1.85)
        except asyncio.TimeoutError:
            continue


def _fallback_queries(topic: str) -> List[str]:
    base = topic.strip().rstrip("?")
    return [
        base,
        f"{base} comprehensive overview background history",
        f"{base} latest news developments 2025 2026",
        f"{base} statistics data research study",
        f"{base} expert analysis perspectives debate",
        f"{base} advantages disadvantages pros cons",
        f"{base} case studies real world examples",
        f"{base} future trends outlook predictions",
        f"{base} comparison alternatives vs",
    ]


async def _plan_queries(topic: str, bot_settings: Optional[BotSettings]) -> List[str]:
    models = await fetch_mistral_models()
    planner = get_model_by_category(models, "fast") or get_model_by_category(models, "general")
    llm = get_llm(streaming=False, bot_settings=bot_settings, model_id=planner, temperature=0.3)
    prompt = (
        f"You are a research planner for Gemini-style deep research. Given a user question, output exactly "
        f"{PLANNED_QUERY_COUNT} diverse web search queries for an exhaustive report. Include: core facts, "
        "background/history, recent news, data/statistics, expert opinions, competing perspectives, "
        "case studies, comparisons/alternatives, future trends, and one query targeting official or primary sources.\n\n"
        f"Research question: {topic}\n\n"
        f"Respond with ONLY a JSON array of {PLANNED_QUERY_COUNT} strings, no markdown."
    )
    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            queries = json.loads(match.group())
            if isinstance(queries, list) and len(queries) >= 3:
                return [str(q).strip() for q in queries[:PLANNED_QUERY_COUNT + 1] if str(q).strip()]
    except Exception:
        pass
    return _fallback_queries(topic)


async def _gap_queries(
    topic: str,
    research_summary: str,
    bot_settings: Optional[BotSettings],
) -> List[str]:
    """Follow-up searches to fill gaps (Gemini-style second pass)."""
    models = await fetch_mistral_models()
    planner = get_model_by_category(models, "fast") or get_model_by_category(models, "general")
    llm = get_llm(streaming=False, bot_settings=bot_settings, model_id=planner, temperature=0.2)
    prompt = (
        "You are a research analyst reviewing partial web results.\n\n"
        f"Original question: {topic}\n\n"
        f"Research collected so far:\n{research_summary[:6000]}\n\n"
        "What important angles are STILL MISSING for a comprehensive Gemini-style deep research report? "
        "Output 2-4 specific web search queries to fill gaps (perspectives, data, case studies, debates).\n"
        "Respond with ONLY a JSON array of strings (max 4). If coverage is truly exhaustive, return []."
    )
    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            queries = json.loads(match.group())
            if isinstance(queries, list):
                return [str(q).strip() for q in queries[:4] if str(q).strip()]
    except Exception:
        pass
    return []


def _merge_results(all_results: List[dict]) -> List[dict]:
    seen: Set[str] = set()
    merged = []
    for r in sorted(all_results, key=lambda x: x.get("score", 0), reverse=True):
        url = r.get("url", "")
        key = url or r.get("title", "")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(r)
    return merged[:MAX_MERGED_SOURCES]


async def _run_search_round(
    queries: List[str],
    step_offset: int,
    total_steps: int,
    all_results: List[dict],
    research_blocks: List[str],
    sources_accumulated: int,
) -> AsyncGenerator[str, None]:
    for i, q in enumerate(queries):
        step = step_offset + i
        yield _research_event(
            "searching",
            random.choice(SEARCH_START),
            step,
            total_steps,
            q,
            label="Searching",
            sources_found=sources_accumulated,
        )
        await asyncio.sleep(0.05)
        try:
            results, provider = search_web_deep(q, max_results=SEARCH_MAX_RESULTS)
            all_results.extend(results)
            block = format_results_for_llm(results, q, provider)
            research_blocks.append(block)
            new_cards = [_source_card(r) for r in results if r.get("url") or r.get("title")]
            sources_accumulated += len(new_cards)
            yield _research_event(
                "searching",
                f"Found {len(results)} sources via {provider}",
                step,
                total_steps,
                q,
                label="Searching",
                sources_found=sources_accumulated,
                new_sources=new_cards[:6],
            )
        except Exception as e:
            yield _research_event(
                "searching",
                f"Search failed: {e}",
                step,
                total_steps,
                q,
                label="Searching",
                sources_found=sources_accumulated,
            )
        await asyncio.sleep(0.08)


def _insufficient_sources_report(topic: str, provider: str, queries_run: int, sources: int) -> str:
    return (
        f"## Deep research could not complete\n\n"
        f"I tried to research **{topic}** on the web but found **{sources} usable source(s)** "
        f"after **{queries_run} searches** (provider: **{provider}**).\n\n"
        "### What you can do\n"
        "1. **Enable better search** — add `TAVILY_API_KEY` to `backend/.env` (free at [tavily.com](https://tavily.com)) "
        "for much more reliable results than DuckDuckGo alone.\n"
        "2. **Check your network** — the backend must reach the internet.\n"
        "3. **Try again** with a more specific question, or use normal chat with **Settings → Web search → Always**.\n\n"
        "Deep research requires live web sources — I won't guess answers without them."
    )


async def _build_report_outline(
    topic: str,
    research_blocks: List[str],
    merged_sources: List[dict],
    provider: str,
    bot_settings: Optional[BotSettings],
) -> str:
    """Pass 1: detailed section outline before full synthesis (Gemini-style depth)."""
    models = await fetch_mistral_models()
    planner = pick_specialist(models, "plan")
    llm = get_llm(
        streaming=False,
        bot_settings=bot_settings,
        model_id=planner,
        temperature=RESEARCH_OUTLINE_TEMPERATURE,
        max_tokens=RESEARCH_OUTLINE_MAX_TOKENS,
    )
    combined = "\n\n---\n\n".join(research_blocks)
    source_count = len(merged_sources)

    prompt = (
        "You are planning a Gemini Deep Research-style report outline.\n\n"
        f"## Research question\n{topic}\n\n"
        f"## Web research gathered ({source_count} sources via {provider})\n{combined}\n\n"
        "Create a **detailed report outline** with **8–12 major sections**. For each section:\n"
        "- Use `## Section Title` for major sections\n"
        "- Add 2–4 `### Subsection` headings under each major section\n"
        "- Under each subsection, list 3–6 bullet points of **specific facts, data points, names, dates, "
        "and angles** to cover, with inline [N] citations referencing source numbers from the research\n"
        "- Plan sections for: executive summary scope, background/context, key concepts in depth, "
        "thematic analysis, data/statistics, multiple perspectives/debates, case studies, comparative analysis, "
        "future outlook, practical implications, gaps/limitations\n\n"
        "The outline must be substantive (500+ words). Do NOT write the full report — only the structured outline."
    )
    resp = await llm.ainvoke([
        SystemMessage(content="You create exhaustive research report outlines. Be thorough and specific."),
        HumanMessage(content=prompt),
    ])
    return resp.content if isinstance(resp.content, str) else str(resp.content)


def _numbered_source_index(merged_sources: List[dict]) -> str:
    numbered_sources = []
    for i, r in enumerate(merged_sources[:MAX_CITATION_SOURCES], start=1):
        card = _source_card(r)
        if card["url"] or card["title"]:
            numbered_sources.append((i, card["title"], card["url"]))
    return "\n".join(
        f"[{n}] {title} — {url}" if url else f"[{n}] {title}"
        for n, title, url in numbered_sources
    )


def _synthesis_system_prompt() -> str:
    return (
        "You are a senior research analyst writing Gemini Deep Research-quality reports. "
        "Your reports are long-form, evidence-based, and exhaustively detailed — never brief summaries, "
        "never shallow bullet skims, never stopping after a short overview. "
        "You write in full paragraphs with nuance, examples, statistics, and multiple perspectives."
    )


def _synthesis_user_prompt(
    topic: str,
    combined: str,
    source_lines: str,
    source_count: int,
    provider: str,
    outline: str,
) -> str:
    return (
        "Write a **comprehensive, in-depth** markdown research report matching the quality and depth of "
        "**Google Gemini Deep Research**.\n\n"
        f"## Original question\n{topic}\n\n"
        f"## Web research gathered ({source_count} sources via {provider})\n{combined}\n\n"
        "## Numbered source index (use these citation numbers in the report body)\n"
        f"{source_lines}\n\n"
        "## Approved report outline (follow this structure; expand every section into full prose)\n"
        f"{outline}\n\n"
        "---\n\n"
        "## REQUIRED REPORT STRUCTURE\n"
        "Write **8–12 major `##` sections** (plus subsections with `###`). Minimum depth targets:\n"
        "- **Broad / multi-faceted topics:** 4000–8000+ words\n"
        "- **Narrow / focused topics:** 2500+ words\n\n"
        "Include ALL of the following (merge related items into thematic sections as appropriate):\n"
        "1. **Executive Summary** — 2–3 concise paragraphs (not the whole report)\n"
        "2. **Table of Contents** — linked markdown list of all major sections\n"
        "3. **Background & Context** — thorough historical and conceptual setup in **full paragraphs**\n"
        "4. **Key Concepts Explained** — define and explain core ideas in depth, not one-line definitions\n"
        "5. **Thematic Deep-Dive Sections** — 3–5 sections each with multiple `###` subsections; "
        "current state, mechanisms, stakeholders, regional/industry angles as relevant\n"
        "6. **Data, Statistics & Timelines** — specific numbers, dates, milestones from sources [N]\n"
        "7. **Multiple Perspectives & Debates** — pros, cons, controversies, competing expert views\n"
        "8. **Case Studies & Real-World Examples** — concrete instances with names, dates, outcomes\n"
        "9. **Comparative Analysis** — vs alternatives, competing approaches, trade-offs\n"
        "10. **Future Outlook & Trends** — forward-looking assessment grounded in sources\n"
        "11. **Practical Implications & Recommendations** — actionable takeaways for the reader\n"
        "12. **Gaps & Limitations** — what the available web evidence does NOT establish\n"
        "13. **Conclusion** — 2–3 synthesizing paragraphs tying everything together\n\n"
        "## CRITICAL DEPTH RULES\n"
        "- **Synthesize ALL gathered sources** — weave facts from every relevant snippet into the narrative.\n"
        "- Write in **substantive paragraphs** (4–8 sentences each). "
        "**FORBIDDEN:** one-sentence sections, shallow bullet-only summaries, or ending after 2 paragraphs.\n"
        "- Bullets are allowed only as supplements inside otherwise detailed sections — never as a substitute for prose.\n"
        "- Cite with bracket numbers [1], [2] inline after claims — NOT markdown links in the body.\n"
        "- Every major claim, statistic, date, and name needs at least one [N] citation.\n"
        "- Include specific numbers, dates, names, and quotes/paraphrases from sources wherever available.\n"
        "- Where sources disagree, present both sides with citations.\n"
        "- Use ONLY facts from the web research above — do NOT fill gaps with pre-trained knowledge.\n"
        "- If evidence is thin on a point, explicitly state 'insufficient web evidence'.\n"
        "- Do **NOT** include a Sources or References section — the app renders source links separately.\n"
        "- Do **NOT** write a premature 'In conclusion' before completing all thematic sections.\n"
        "- Expand the approved outline into full prose — do not copy the outline bullets verbatim; elaborate each point."
    )


async def _expand_report(
    topic: str,
    report: str,
    research_blocks: List[str],
    merged_sources: List[dict],
    provider: str,
    bot_settings: Optional[BotSettings],
    outline: str,
    target_words: int,
    pass_num: int,
) -> str:
    """Additional pass when synthesis stopped too early (common with Mistral)."""
    models = await fetch_mistral_models()
    writer = pick_specialist(models, "synthesis")
    llm = get_llm(
        streaming=False,
        bot_settings=bot_settings,
        model_id=writer,
        temperature=RESEARCH_WRITER_TEMPERATURE,
        max_tokens=RESEARCH_EXPAND_MAX_TOKENS,
    )
    combined = "\n\n---\n\n".join(research_blocks)
    source_lines = _numbered_source_index(merged_sources)
    current_words = _word_count(report)
    sections = _major_section_count(report)

    prompt = (
        f"## Expansion pass {pass_num} — report is too short\n\n"
        f"The draft below is only **{current_words} words** with **{sections} major sections**, "
        f"but the target is **{target_words}+ words** with **8–12 major `##` sections**.\n\n"
        f"## Original question\n{topic}\n\n"
        f"## Web research ({len(merged_sources)} sources via {provider})\n{combined}\n\n"
        "## Numbered source index\n"
        f"{source_lines}\n\n"
        "## Approved outline (ensure every section is fully covered)\n"
        f"{outline}\n\n"
        "## Current draft (expand — do NOT replace with a shorter summary)\n"
        f"{report}\n\n"
        "---\n\n"
        "## YOUR TASK\n"
        "Return the **complete expanded report** (not a diff). Requirements:\n"
        f"- Reach at least **{target_words} words** — add substantive paragraphs, not filler.\n"
        "- Expand **every existing section** with more prose, data, examples, and citations [N].\n"
        "- Add missing `##` sections from the outline if the draft skipped any.\n"
        "- Each major section needs multiple `###` subsections and 4–8 sentence paragraphs.\n"
        "- **FORBIDDEN:** shortening, summarizing what you already wrote, or bullet-only sections.\n"
        "- Keep all valid [N] citations; add more where you introduce new facts from sources.\n"
        "- Do NOT include a Sources/References section."
    )
    resp = await llm.ainvoke([
        SystemMessage(content=_synthesis_system_prompt()),
        HumanMessage(content=prompt),
    ])
    expanded = resp.content if isinstance(resp.content, str) else str(resp.content)
    return expanded if expanded.strip() else report


async def _synthesize_report(
    topic: str,
    research_blocks: List[str],
    merged_sources: List[dict],
    provider: str,
    bot_settings: Optional[BotSettings],
    outline: str,
) -> str:
    models = await fetch_mistral_models()
    writer = pick_specialist(models, "synthesis")
    llm = get_llm(
        streaming=False,
        bot_settings=bot_settings,
        model_id=writer,
        temperature=RESEARCH_WRITER_TEMPERATURE,
        max_tokens=RESEARCH_MAX_TOKENS,
    )
    combined = "\n\n---\n\n".join(research_blocks)
    source_lines = _numbered_source_index(merged_sources)

    prompt = _synthesis_user_prompt(
        topic, combined, source_lines, len(merged_sources), provider, outline
    )
    resp = await llm.ainvoke([
        SystemMessage(content=_synthesis_system_prompt()),
        HumanMessage(content=prompt),
    ])
    return resp.content if isinstance(resp.content, str) else str(resp.content)


async def _produce_report(
    topic: str,
    research_blocks: List[str],
    merged_sources: List[dict],
    provider: str,
    bot_settings: Optional[BotSettings],
) -> str:
    """Multi-pass: outline → synthesis → expansion if too short."""
    outline = await _build_report_outline(
        topic, research_blocks, merged_sources, provider, bot_settings
    )
    report = await _synthesize_report(
        topic, research_blocks, merged_sources, provider, bot_settings, outline
    )
    target_words = _report_word_target(topic)
    for pass_num in range(1, MAX_EXPANSION_PASSES + 1):
        words = _word_count(report)
        sections = _major_section_count(report)
        needs_words = words < int(target_words * 0.85)
        needs_sections = sections < 7
        if not needs_words and not needs_sections:
            break
        report = await _expand_report(
            topic,
            report,
            research_blocks,
            merged_sources,
            provider,
            bot_settings,
            outline,
            target_words,
            pass_num,
        )
    return report


async def stream_deep_research(
    topic: str,
    bot_settings: Optional[BotSettings] = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE: progress events, then report tokens. Always uses live web search."""
    provider = get_active_provider()
    yield _sse({
        "meta": f"Deep research · Web search: {provider} (always on for this mode)",
        "research_meta": {"provider": provider, "web_forced": True},
    })

    plan_task = asyncio.create_task(_plan_queries(topic, bot_settings))
    async for event in _tick_while_waiting(plan_task, "planning", PLANNING_TICKS, 0, 0):
        yield event
    queries = plan_task.result()

    # News pass for recency
    news_queries = [f"{topic.strip().rstrip('?')} news", f"{topic.strip().rstrip('?')} latest 2026"]
    all_planned = queries + news_queries[:1]
    gap_slots = 3
    total_steps = len(all_planned) + gap_slots + 3

    yield _research_event(
        "planning",
        f"Running {len(all_planned)} web searches + gap analysis",
        1,
        total_steps,
        label="Thinking",
    )

    all_results: List[dict] = []
    research_blocks: List[str] = []
    queries_run = 0
    sources_found = 0

    async for event in _run_search_round(
        all_planned, 2, total_steps, all_results, research_blocks, len(_merge_results(all_results))
    ):
        yield event
    queries_run = len(all_planned)
    sources_found = len(_merge_results(all_results))

    # News articles
    yield _research_event(
        "searching",
        "Searching recent news…",
        len(all_planned) + 2,
        total_steps,
        label="Searching",
        sources_found=sources_found,
    )
    news = search_news(topic, max_results=8)
    if news:
        all_results.extend(news)
        research_blocks.append(format_results_for_llm(news, f"{topic} news", "duckduckgo_news"))
        news_cards = [_source_card(r) for r in news if r.get("url") or r.get("title")]
        sources_found += len(news_cards)
        yield _research_event(
            "searching",
            f"Found {len(news)} news articles",
            len(all_planned) + 2,
            total_steps,
            label="Searching",
            sources_found=sources_found,
            new_sources=news_cards[:6],
        )

    merged = _merge_results(all_results)

    # Gap analysis + follow-up searches
    summary_for_gap = format_results_for_llm(merged[:18], topic, "summary") if merged else "No results yet."
    analyze_task = asyncio.create_task(_gap_queries(topic, summary_for_gap, bot_settings))
    async for event in _tick_while_waiting(
        analyze_task,
        "analyzing",
        ANALYZING_TICKS,
        total_steps - 2,
        total_steps,
    ):
        yield event
    follow_ups = analyze_task.result()

    if follow_ups:
        async for event in _run_search_round(
            follow_ups,
            total_steps - 2,
            total_steps,
            all_results,
            research_blocks,
            len(_merge_results(all_results)),
        ):
            yield event
        queries_run += len(follow_ups)
        merged = _merge_results(all_results)
        sources_found = len(merged)

    source_list = [_source_card(r) for r in merged if r.get("url") or r.get("title")]

    yield _research_event(
        "analyzing",
        f"Reviewed {len(merged)} unique web sources",
        total_steps - 1,
        total_steps,
        label="Analyzing",
        sources_found=len(source_list),
    )
    yield _sse({
        "research_meta": {
            "provider": provider,
            "sources": len(merged),
            "queries": queries_run + (1 if news else 0),
            "source_list": source_list[:MAX_MERGED_SOURCES],
        }
    })

    if len(merged) < MIN_SOURCES:
        report = _insufficient_sources_report(topic, provider, queries_run, len(merged))
        yield _research_event(
            "complete",
            f"Insufficient web sources ({len(merged)} found)",
            total_steps,
            total_steps,
            label="Done",
        )
        for i in range(0, len(report), 8):
            yield _sse({"token": report[i : i + 8]})
        return

    summary_block = format_results_for_llm(merged[:22], topic, provider, start_index=1)
    research_blocks.insert(0, summary_block)

    write_task = asyncio.create_task(
        _produce_report(topic, research_blocks, merged, provider, bot_settings)
    )
    async for event in _tick_while_waiting(write_task, "writing", WRITING_TICKS, total_steps, total_steps):
        yield event
    report = write_task.result()

    yield _research_event(
        "complete",
        f"Research complete — {len(merged)} sources cited",
        total_steps,
        total_steps,
        label="Done",
    )

    chunk_size = 8
    for i in range(0, len(report), chunk_size):
        yield _sse({"token": report[i : i + chunk_size]})
        if i % 80 == 0:
            await asyncio.sleep(0.01)
