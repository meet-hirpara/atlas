"""Composer model presets: display names, Mistral IDs, and behavior profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

ModelProfile = Literal["general", "code", "creative"]

DEFAULT_COMPOSER_MODEL_ID = "mistral-large"


@dataclass(frozen=True)
class ComposerModel:
    id: str
    display_name: str
    mistral_id: str
    profile: ModelProfile
    description: str


COMPOSER_MODELS: dict[str, ComposerModel] = {
    "mistral-large": ComposerModel(
        id="mistral-large",
        display_name="Fable 5",
        mistral_id="mistral-large-latest",
        profile="general",
        description="Powerful general assistant for reasoning and Q&A",
    ),
    "mistral-code": ComposerModel(
        id="mistral-code",
        display_name="Mistral Code",
        mistral_id="codestral-latest",
        profile="code",
        description="Code-focused — concise, technical, implementation-first",
    ),
    "gpt-5.6": ComposerModel(
        id="gpt-5.6",
        display_name="GPT 5.6",
        mistral_id="mistral-large-latest",
        profile="creative",
        description="Creative and balanced — exploratory, vivid answers",
    ),
}


def list_composer_models() -> list[ComposerModel]:
    return list(COMPOSER_MODELS.values())


def get_composer_model(selection: str) -> Optional[ComposerModel]:
    return COMPOSER_MODELS.get(selection)


def resolve_mistral_model_id(selection: str) -> Optional[str]:
    preset = get_composer_model(selection)
    if preset:
        return preset.mistral_id
    if selection and selection != "auto":
        return selection
    return None


def resolve_effective_composer_selection(selection: str) -> str:
    if not selection or selection == "auto":
        return DEFAULT_COMPOSER_MODEL_ID
    return selection


def resolve_model_profile(selection: str) -> Optional[ModelProfile]:
    preset = get_composer_model(resolve_effective_composer_selection(selection))
    return preset.profile if preset else None
