"""Tests for composer model registry and routing."""

from app.services.model_display_service import (
    encode_model_message,
    parse_model_display,
    resolve_model_display,
    strip_model_message,
)
from app.services.model_registry import resolve_mistral_model_id
from app.services.model_router import build_routing_plan
from app.services.prompt_builder import get_temperature
from app.models.bot_settings import BotSettings


def test_composer_preset_mistral_mapping():
    assert resolve_mistral_model_id("mistral-large") == "mistral-large-latest"
    assert resolve_mistral_model_id("mistral-code") == "codestral-latest"
    assert resolve_mistral_model_id("gpt-5.6") == "mistral-large-latest"


def test_composer_display_names():
    assert resolve_model_display("mistral-large") == "Fable 5"
    assert resolve_model_display("mistral-code") == "Mistral Code"
    assert resolve_model_display("gpt-5.6") == "GPT 5.6"


def test_model_message_roundtrip():
    encoded = encode_model_message("Hello world", "Fable 5")
    assert parse_model_display(encoded) == "Fable 5"
    assert strip_model_message(encoded) == "Hello world"


def test_strip_model_message_without_marker():
    assert strip_model_message("plain text") == "plain text"


def test_encode_model_message_empty_content_is_marker_only():
    encoded = encode_model_message("", "Fable 5")
    assert strip_model_message(encoded) == ""
    assert parse_model_display(encoded) == "Fable 5"


def test_routing_plan_uses_resolved_mistral_id():
    plan = build_routing_plan("hello", [], "mistral-code")
    assert plan.mode == "single"
    assert plan.primary_model == "codestral-latest"
    assert "Mistral Code" in plan.explanation


def test_profile_temperature_overrides():
    code_settings = BotSettings(model_selection="mistral-code")
    creative_settings = BotSettings(model_selection="gpt-5.6")
    assert get_temperature(code_settings) == 0.2
    assert get_temperature(creative_settings) == 0.85
