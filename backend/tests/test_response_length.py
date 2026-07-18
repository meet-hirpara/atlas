"""Tests for response length settings end-to-end."""

from app.models.bot_settings import BotSettings
from app.services.llm_service import get_max_tokens
from app.services.model_registry import resolve_model_profile
from app.services.prompt_builder import build_system_prompt


def test_detailed_prompt_includes_mandatory_length_block():
    settings = BotSettings(responseLength="detailed", modelSelection="mistral-large")
    prompt = build_system_prompt(settings)
    assert "MANDATORY — user setting: Detailed" in prompt
    assert "thorough, in-depth" in prompt


def test_detailed_skips_code_brevity_style():
    settings = BotSettings(responseLength="detailed", modelSelection="mistral-code")
    prompt = build_system_prompt(settings)
    assert "MANDATORY — user setting: Detailed" in prompt
    assert "Keep prose minimal" not in prompt


def test_brief_code_profile_keeps_minimal_style():
    settings = BotSettings(responseLength="brief", modelSelection="mistral-code")
    prompt = build_system_prompt(settings)
    assert "Keep prose minimal" in prompt
    assert "MANDATORY — user setting: Detailed" not in prompt


def test_auto_model_resolves_general_profile():
    settings = BotSettings(responseLength="detailed", modelSelection="auto")
    assert resolve_model_profile("auto") == "general"


def test_detailed_max_tokens_at_least_8192_for_general():
    settings = BotSettings(responseLength="detailed", modelSelection="mistral-large")
    assert get_max_tokens(settings) >= 12288


def test_auto_detailed_gets_high_max_tokens():
    settings = BotSettings(responseLength="detailed", modelSelection="auto")
    assert get_max_tokens(settings) >= 12288


def test_detailed_enforcement_requires_min_sections():
    settings = BotSettings(responseLength="detailed", modelSelection="mistral-large")
    prompt = build_system_prompt(settings)
    assert "5 `##` sections" in prompt
    assert "FORBIDDEN" in prompt
    assert "800–2000+" in prompt
