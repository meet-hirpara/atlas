"""Unit tests for deep research helpers (no live API)."""

from app.services.deep_research_service import (
    MAX_EXPANSION_PASSES,
    MAX_MERGED_SOURCES,
    MIN_BROAD_REPORT_WORDS,
    MIN_NARROW_REPORT_WORDS,
    PLANNED_QUERY_COUNT,
    RESEARCH_WRITER_TEMPERATURE,
    _major_section_count,
    _merge_results,
    _numbered_source_index,
    _report_word_target,
    _synthesis_user_prompt,
    _word_count,
)


def test_merge_results_dedupes_and_caps():
    results = [
        {"url": "https://a.com", "title": "A", "score": 0.9},
        {"url": "https://a.com", "title": "A dup", "score": 0.8},
        {"url": "https://b.com", "title": "B", "score": 0.7},
    ]
    merged = _merge_results(results)
    assert len(merged) == 2
    assert merged[0]["url"] == "https://a.com"


def test_merge_results_respects_max_cap():
    results = [{"url": f"https://x{i}.com", "title": f"T{i}", "score": i} for i in range(40)]
    merged = _merge_results(results)
    assert len(merged) == MAX_MERGED_SOURCES


def test_numbered_source_index_formats_citations():
    sources = [
        {"url": "https://example.com", "title": "Example"},
        {"url": "", "title": "No URL"},
    ]
    text = _numbered_source_index(sources)
    assert "[1] Example — https://example.com" in text
    assert "[2] No URL" in text


def test_synthesis_prompt_requires_gemini_depth():
    prompt = _synthesis_user_prompt(
        topic="AI regulation",
        combined="## research block",
        source_lines="[1] Source — https://x.com",
        source_count=5,
        provider="tavily",
        outline="## Executive Summary\n- point [1]",
    )
    assert "4000–8000+" in prompt
    assert "8–12 major" in prompt
    assert "FORBIDDEN" in prompt
    assert "Gemini Deep Research" in prompt


def test_planned_query_count_at_least_eight():
    assert PLANNED_QUERY_COUNT >= 8


def test_writer_temperature_in_depth_range():
    assert 0.5 <= RESEARCH_WRITER_TEMPERATURE <= 0.7


def test_word_count_and_section_helpers():
    text = "## One\n\nHello world.\n\n## Two\n\nMore content here."
    assert _word_count(text) >= 5
    assert _major_section_count(text) == 2


def test_report_word_target_broad_vs_narrow():
    assert _report_word_target("compare AI regulation vs EU law") >= MIN_BROAD_REPORT_WORDS
    assert _report_word_target("what is Python") == MIN_NARROW_REPORT_WORDS


def test_expansion_passes_configured():
    assert MAX_EXPANSION_PASSES >= 2
