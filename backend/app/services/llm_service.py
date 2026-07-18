from typing import Optional

from langchain_mistralai import ChatMistralAI

from app.config import get_settings
from app.models.bot_settings import BotSettings
from app.services.model_registry import resolve_mistral_model_id, resolve_model_profile, resolve_model_profile
from app.services.prompt_builder import get_temperature

settings = get_settings()

_LENGTH_MAX_TOKENS = {
    "brief": 2048,
    "balanced": 4096,
    "detailed": 12288,
}

# Mistral Large supports large outputs; 20k tokens ≈ 12–15k words headroom for deep research.
RESEARCH_MAX_TOKENS = 20480
RESEARCH_OUTLINE_MAX_TOKENS = 6144
RESEARCH_EXPAND_MAX_TOKENS = 16384


def get_max_tokens(bot_settings: Optional[BotSettings] = None) -> int:
    s = bot_settings or BotSettings()
    length = s.response_length
    profile = resolve_model_profile(s.model_selection)
    base = _LENGTH_MAX_TOKENS.get(length, 4096)

    if profile == "creative" and length == "detailed":
        return max(base, 6144)
    if profile == "code":
        if length == "detailed":
            return max(base, 6144)
        if length == "balanced":
            return 4096
        return 2048
    return base


def get_llm(
    streaming: bool = True,
    bot_settings: Optional[BotSettings] = None,
    model_id: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatMistralAI:
    selection = (
        bot_settings.model_selection
        if bot_settings and bot_settings.model_selection != "auto"
        else None
    )
    resolved_selection = resolve_mistral_model_id(model_id) if model_id else None
    model = resolved_selection or (
        resolve_mistral_model_id(selection or "")
        if selection
        else None
    ) or settings.mistral_model
    # Always map composer preset ids (e.g. mistral-large) to real Mistral API ids.
    model = resolve_mistral_model_id(model or "") or model or settings.mistral_model
    if model and "ocr" in model.lower():
        model = settings.mistral_model
    temp = temperature if temperature is not None else get_temperature(bot_settings)
    kwargs: dict = {
        "model": model,
        "mistral_api_key": settings.mistral_api_key,
        "streaming": streaming,
        "temperature": temp,
        "max_tokens": max_tokens if max_tokens is not None else get_max_tokens(bot_settings),
    }
    return ChatMistralAI(**kwargs)
