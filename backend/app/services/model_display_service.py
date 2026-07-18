"""User-facing model display names (Claude-style labels in chat UI)."""

from __future__ import annotations

import json
from typing import Optional

from app.services.model_registry import (
    DEFAULT_COMPOSER_MODEL_ID,
    get_composer_model,
    list_composer_models,
)

MODEL_MARKER_PREFIX = "<!--nexus-model:"
MODEL_MARKER_SUFFIX = "-->"

DEFAULT_DISPLAY_NAME = "Fable 5"
EXTENDED_DISPLAY_NAME = "Fable 5 Extended"


def resolve_model_display(
    model_id: str = "",
    orchestrated: bool = False,
    deep_research: bool = False,
) -> str:
    if orchestrated:
        return EXTENDED_DISPLAY_NAME
    preset = get_composer_model(model_id)
    if preset:
        return preset.display_name
    if model_id == "auto":
        return "Auto"
    if model_id:
        return model_id
    default = get_composer_model(DEFAULT_COMPOSER_MODEL_ID)
    return default.display_name if default else DEFAULT_DISPLAY_NAME


def list_composer_model_options() -> list[dict]:
    return [
        {
            "id": m.id,
            "displayName": m.display_name,
            "mistralId": m.mistral_id,
            "profile": m.profile,
            "description": m.description,
        }
        for m in list_composer_models()
    ]


def encode_model_message(content: str, display_name: str) -> str:
    if not display_name:
        return content
    marker = f"{MODEL_MARKER_PREFIX}{json.dumps(display_name, ensure_ascii=False)}{MODEL_MARKER_SUFFIX}"
    return f"{content.rstrip()}\n{marker}"


def parse_model_display(content: str) -> Optional[str]:
    start = content.find(MODEL_MARKER_PREFIX)
    if start < 0:
        return None
    json_start = start + len(MODEL_MARKER_PREFIX)
    end = content.find(MODEL_MARKER_SUFFIX, json_start)
    if end < 0:
        return None
    try:
        name = json.loads(content[json_start:end])
        return str(name) if name else None
    except json.JSONDecodeError:
        return None


def strip_model_message(content: str) -> str:
    start = content.find(MODEL_MARKER_PREFIX)
    if start < 0:
        return content.strip()
    return content[:start].strip()
