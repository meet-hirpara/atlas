import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings

settings = get_settings()

DEFAULT_CHAT_MODELS = [
    {"id": "mistral-large-latest", "name": "Mistral Large", "category": "general", "model_type": "chat", "description": "Best for reasoning & QA"},
    {"id": "mistral-small-latest", "name": "Mistral Small", "category": "fast", "model_type": "chat", "description": "Fast, lightweight tasks"},
    {"id": "codestral-latest", "name": "Codestral", "category": "code", "model_type": "chat", "description": "Code generation & debugging"},
    {"id": "pixtral-large-latest", "name": "Pixtral Large", "category": "vision", "model_type": "chat", "description": "Design, diagrams & vision"},
    {"id": "ministral-8b-latest", "name": "Ministral 8B", "category": "fast", "model_type": "chat", "description": "Ultra-fast responses"},
]

DEFAULT_OCR_MODELS = [
    {"id": "mistral-ocr-latest", "name": "Mistral OCR (latest)", "category": "ocr", "model_type": "ocr", "description": "Best document OCR — PDFs, scans, tables"},
    {"id": "mistral-ocr-4-0", "name": "Mistral OCR 4", "category": "ocr", "model_type": "ocr", "description": "OCR 4 with bounding boxes & confidence scores"},
]

_cache: Dict[str, Any] = {"chat": [], "ocr": [], "fetched_at": 0}
CACHE_TTL = 3600


def _is_ocr_model(model_id: str) -> bool:
    return "ocr" in model_id.lower()


def _categorize(model_id: str, capabilities: Optional[dict] = None) -> str:
    mid = model_id.lower()
    if _is_ocr_model(mid):
        return "ocr"
    if "embed" in mid:
        return "embedding"
    if "codestral" in mid or "code" in mid:
        return "code"
    if "pixtral" in mid or (capabilities and capabilities.get("vision")):
        return "vision"
    if "ministral" in mid or "tiny" in mid or "small" in mid:
        return "fast"
    if "large" in mid or "medium" in mid:
        return "general"
    return "general"


def _is_chat_model(model_id: str, capabilities: Optional[dict] = None) -> bool:
    if _is_ocr_model(model_id):
        return False
    if "embed" in model_id.lower() or "moderation" in model_id.lower():
        return False
    if capabilities and capabilities.get("completion_chat") is False:
        return False
    return True


def _model_entry(m: dict) -> dict:
    model_id = m.get("id", "")
    caps = m.get("capabilities") or {}
    is_ocr = _is_ocr_model(model_id)
    return {
        "id": model_id,
        "name": m.get("name") or model_id,
        "category": _categorize(model_id, caps),
        "model_type": "ocr" if is_ocr else "chat",
        "description": m.get("description") or ("Document OCR & text extraction" if is_ocr else ""),
        "max_context_length": m.get("max_context_length"),
    }


async def _fetch_raw_models() -> List[dict]:
    now = time.time()
    if _cache["chat"] and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["chat"] + _cache["ocr"]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("data", data) if isinstance(data, dict) else data
            entries = [_model_entry(m) for m in raw]
            chat = [e for e in entries if e["model_type"] == "chat" and _is_chat_model(e["id"])]
            ocr = [e for e in entries if e["model_type"] == "ocr"]
            chat.sort(key=lambda x: (x["category"], x["id"]))
            ocr.sort(key=lambda x: x["id"], reverse=True)
            if chat or ocr:
                _cache["chat"] = chat or DEFAULT_CHAT_MODELS
                _cache["ocr"] = ocr or DEFAULT_OCR_MODELS
                _cache["fetched_at"] = now
                return _cache["chat"] + _cache["ocr"]
    except Exception:
        pass

    return DEFAULT_CHAT_MODELS + DEFAULT_OCR_MODELS


async def fetch_mistral_models() -> List[dict]:
    all_models = await _fetch_raw_models()
    return [m for m in all_models if m["model_type"] == "chat"]


async def fetch_ocr_models() -> List[dict]:
    all_models = await _fetch_raw_models()
    ocr = [m for m in all_models if m["model_type"] == "ocr"]
    return ocr or DEFAULT_OCR_MODELS


def resolve_ocr_model(selection: str = "auto") -> str:
    ocr_models = _cache.get("ocr") or DEFAULT_OCR_MODELS
    if selection and selection != "auto":
        return selection
    for preferred in ("mistral-ocr-latest", "mistral-ocr-4-0", "mistral-ocr-4"):
        for m in ocr_models:
            if m["id"] == preferred:
                return preferred
    if ocr_models:
        return ocr_models[0]["id"]
    return "mistral-ocr-latest"


def get_model_by_category(models: List[dict], category: str) -> Optional[str]:
    for m in models:
        if m["category"] == category:
            return m["id"]
    return None


def pick_specialist(models: List[dict], task_type: str) -> str:
    mapping = {
        "code": "code",
        "design": "vision",
        "diagram": "vision",
        "vision": "vision",
        "ocr": "ocr",
        "document": "ocr",
        "fast": "fast",
        "plan": "fast",
        "general": "general",
        "qa": "general",
        "reasoning": "general",
        "synthesis": "general",
    }
    cat = mapping.get(task_type, "general")
    if cat == "ocr":
        return resolve_ocr_model("auto")
    model_id = get_model_by_category(models, cat)
    if model_id:
        return model_id
    return get_model_by_category(models, "general") or settings.mistral_model
