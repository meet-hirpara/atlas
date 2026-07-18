from fastapi import APIRouter

from app.services.model_display_service import list_composer_model_options
from app.services.model_service import fetch_mistral_models, fetch_ocr_models

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_models():
    chat_models = await fetch_mistral_models()
    ocr_models = await fetch_ocr_models()
    return {
        "models": chat_models,
        "composer_models": list_composer_model_options(),
        "ocr_models": ocr_models,
        "auto": {
            "id": "auto",
            "name": "Auto",
            "category": "auto",
            "description": "Routes to the best model per task (Fugu-style orchestration)",
        },
        "ocr_auto": {
            "id": "auto",
            "name": "Auto",
            "category": "ocr",
            "description": "Uses the best available Mistral OCR model for PDF extraction",
        },
    }
