from fastapi import APIRouter

from app.config import get_settings
from app.services.web_search_service import get_active_provider

router = APIRouter(prefix="/api/web-search", tags=["web-search"])
settings = get_settings()


@router.get("/status")
def web_search_status():
    provider = get_active_provider()
    return {
        "enabled": True,
        "provider": provider,
        "tavily_configured": bool(settings.tavily_api_key),
        "hint": (
            "Add TAVILY_API_KEY to backend/.env for higher-quality AI search (free tier at tavily.com)"
            if not settings.tavily_api_key
            else "Using Tavily AI search (best accuracy)"
        ),
    }
