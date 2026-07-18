"""Detect ambiguous requests and emit structured clarification options."""

import json
import re
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.models.bot_settings import BotSettings
from app.services.llm_service import get_llm

CLARIFICATION_MARKER = "<!--nexus-clarify:"
CLARIFICATION_END = "-->"

_CHECK_PROMPT = """You decide whether the user's latest message needs clarification before an AI assistant can help well.

Return ONLY valid JSON — no markdown, no extra text.

If the request is clear enough to answer directly:
{"needs_clarification": false}

If important details are missing, scope is unclear, or multiple valid approaches exist:
{"needs_clarification": true, "question": "One focused question", "options": ["Option A", "Option B", "Option C"], "allowCustom": true}

Rules:
- Do NOT clarify greetings, thanks, or simple factual questions with one obvious answer.
- DO clarify when: vague pronouns ("this", "it", "that") without clear referent, missing tech stack/version, unclear goal, or several equally valid interpretations.
- Offer 2–4 concrete, distinct options (not yes/no unless that is the real choice).
- Set allowCustom to true so the user can type their own answer.
- Keep the question short and actionable."""

_TRIVIAL_RE = re.compile(
    r"^(?:hi|hello|hey|thanks|thank you|ok(?:ay)?|yes|no|bye|good\s+(?:morning|night)|"
    r"how are you|what(?:'s| is) up)\b",
    re.I,
)

_SIMPLE_FACT_RE = re.compile(
    r"^(?:what is|what's|who is|who's|define|explain)\s+[\w\s\-]{2,50}\??$",
    re.I,
)

_AMBIGUITY_RE = re.compile(
    r"\b("
    r"this|that|it|these|those|"
    r"fix(?:\s+it)?|help(?:\s+me)?|improve|optimize|update|change|"
    r"make\s+it\s+better|not\s+working|doesn'?t\s+work|"
    r"something|anything|stuff|"
    r"or\s+something|either|both|"
    r"which\s+(?:one|way|option|approach)|"
    r"best\s+way|how\s+do\s+i|how\s+should\s+i"
    r")\b",
    re.I,
)

_VAGUE_SHORT_RE = re.compile(
    r"^(?:fix|help|debug|improve|update|change|optimize|refactor|build|create|make)\b",
    re.I,
)


def is_clarification_content(content: str) -> bool:
    return CLARIFICATION_MARKER in content


def parse_clarification(content: str) -> Optional[dict]:
    start = content.find(CLARIFICATION_MARKER)
    if start < 0:
        return None
    json_start = start + len(CLARIFICATION_MARKER)
    end = content.find(CLARIFICATION_END, json_start)
    if end < 0:
        return None
    try:
        payload = json.loads(content[json_start:end])
    except json.JSONDecodeError:
        return None
    if not payload.get("question") or not payload.get("options"):
        return None
    return {
        "question": str(payload["question"]),
        "options": [str(o) for o in payload["options"][:6]],
        "allowCustom": bool(payload.get("allowCustom", True)),
    }


def encode_clarification_message(payload: dict) -> str:
    body = {
        "question": payload["question"],
        "options": payload["options"],
        "allowCustom": payload.get("allowCustom", True),
    }
    return f"{payload['question']}\n{CLARIFICATION_MARKER}{json.dumps(body, ensure_ascii=False)}{CLARIFICATION_END}"


def clarification_event(payload: dict) -> str:
    return f"data: {json.dumps({'clarification': payload})}\n\n"


def is_complex_query(message: str) -> bool:
    text = (message or "").strip()
    if len(text) < 80:
        return False
    if text.count("\n") >= 2:
        return True
    if len(text) > 220:
        return True
    return bool(
        re.search(
            r"\b(and|also|multiple|compare|versus|vs\.?|step(?:s)?|plan|design|implement|"
            r"build|refactor|architecture|requirements|trade-?offs?)\b",
            text,
            re.I,
        )
    )


def _is_trivial(message: str) -> bool:
    text = message.strip()
    if not text:
        return True
    if _TRIVIAL_RE.match(text):
        return True
    if _SIMPLE_FACT_RE.match(text):
        return True
    if len(text) < 18 and "?" not in text:
        return True
    return False


def _has_ambiguity_signals(message: str, recent_history: List[tuple[str, str]]) -> bool:
    text = message.strip()
    if _AMBIGUITY_RE.search(text):
        return True
    if len(text) < 40 and _VAGUE_SHORT_RE.match(text):
        return True
    if re.search(r"\b(this|that|it)\b", text, re.I) and not recent_history:
        return True
    return False


def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


async def check_clarification_needed(
    user_message: str,
    recent_history: List[tuple[str, str]],
    bot_settings: Optional[BotSettings] = None,
) -> Optional[dict]:
    """Return clarification payload if the request is ambiguous, else None."""
    if _is_trivial(user_message):
        return None

    should_check = _has_ambiguity_signals(user_message, recent_history)
    if not should_check and len(user_message.strip()) < 80:
        return None

    context_lines = []
    for role, content in recent_history[-6:]:
        label = "User" if role == "user" else "Assistant"
        snippet = content[:400].replace("\n", " ")
        context_lines.append(f"{label}: {snippet}")

    user_block = (
        f"Recent conversation:\n" + "\n".join(context_lines) + f"\n\nLatest user message:\n{user_message}"
        if context_lines
        else f"User message:\n{user_message}"
    )

    llm = get_llm(streaming=False, bot_settings=bot_settings, temperature=0.2)
    response = await llm.ainvoke(
        [
            SystemMessage(content=_CHECK_PROMPT),
            HumanMessage(content=user_block),
        ]
    )
    raw = response.content if isinstance(response.content, str) else str(response.content)
    data = _extract_json(raw)
    if not data or not data.get("needs_clarification"):
        return None

    question = str(data.get("question", "")).strip()
    options = data.get("options") or []
    options = [str(o).strip() for o in options if str(o).strip()][:4]
    if not question or len(options) < 2:
        return None

    return {
        "question": question,
        "options": options,
        "allowCustom": bool(data.get("allowCustom", True)),
    }
