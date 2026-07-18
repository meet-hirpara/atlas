"""Diagram rendering — local-first; mermaid.ink is opt-in via ATLAS_ALLOW_MERMAID_INK."""

from __future__ import annotations

import base64
import logging
import re
import zlib

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

MERMAID_INK_BASE = "https://mermaid.ink/svg"


def sanitize_mermaid(code: str) -> str:
    result = code.strip()

    result = re.sub(
        r"(\w+)\[([^\]\"]+)\]",
        lambda m: (
            f'{m.group(1)}["{m.group(2).replace(chr(34), "#quot;")}"]'
            if re.search(r"[&()\/=<>#:;]", m.group(2))
            else m.group(0)
        ),
        result,
    )

    result = re.sub(
        r"(\w+)\{([^}\"]+)\}",
        lambda m: (
            f'{m.group(1)}{{"{m.group(2).replace(chr(34), "#quot;")}"}}'
            if re.search(r"[&()\/=<>#:;]", m.group(2))
            else m.group(0)
        ),
        result,
    )

    result = re.sub(r"%%.*$", "", result, flags=re.MULTILINE)
    result = re.sub(r"^\s*(click|call)\s+.*$", "", result, flags=re.MULTILINE | re.IGNORECASE)
    result = re.sub(r"javascript\s*:", "blocked:", result, flags=re.IGNORECASE)
    return result.strip()


def _pako_encode(code: str) -> str:
    compressed = zlib.compress(code.encode("utf-8"), 9)
    return base64.urlsafe_b64encode(compressed).decode("ascii")


async def render_mermaid_svg(code: str) -> str:
    sanitized = sanitize_mermaid(code)
    settings = get_settings()

    if not settings.atlas_allow_mermaid_ink:
        logger.info("Diagram render refused remote mermaid.ink (ATLAS_ALLOW_MERMAID_INK=false)")
        raise ValueError(
            "Remote diagram rendering is disabled. "
            "The frontend renders Mermaid locally. "
            "Set ATLAS_ALLOW_MERMAID_INK=true only if you accept sending diagram source to mermaid.ink."
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        for url in (
            f"{MERMAID_INK_BASE}/pako:{_pako_encode(sanitized)}",
            f"{MERMAID_INK_BASE}/{base64.urlsafe_b64encode(sanitized.encode()).decode('ascii')}",
        ):
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and "<svg" in resp.text.lower():
                    return resp.text
            except httpx.HTTPError as exc:
                logger.warning("mermaid.ink request failed: %s", exc)
                continue

    raise ValueError("Failed to render diagram as SVG")
