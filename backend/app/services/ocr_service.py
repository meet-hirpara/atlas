import base64
from typing import List, Optional, Tuple

import httpx

from app.config import get_settings
from app.services.model_service import resolve_ocr_model

settings = get_settings()
OCR_ENDPOINT = "https://api.mistral.ai/v1/ocr"


def _encode_pdf_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_pdf_with_ocr(
    path: str,
    model_id: Optional[str] = None,
    table_format: str = "markdown",
) -> Tuple[str, int]:
    """
    Extract text from a PDF using Mistral OCR API.
    Returns (markdown_text, page_count).
    """
    model = model_id or resolve_ocr_model("auto")
    b64 = _encode_pdf_base64(path)

    payload = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{b64}",
        },
        "table_format": table_format,
        "include_image_base64": False,
    }

    with httpx.Client(timeout=300.0) as client:
        resp = client.post(
            OCR_ENDPOINT,
            headers={
                "Authorization": f"Bearer {settings.mistral_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    pages = data.get("pages", [])
    parts: List[str] = []
    for i, page in enumerate(pages):
        md = page.get("markdown", "").strip()
        if md:
            parts.append(f"[Page {i + 1}]\n{md}")

    full_text = "\n\n".join(parts)
    page_count = data.get("usage_info", {}).get("pages_processed") or len(pages) or 1
    return full_text, int(page_count)
