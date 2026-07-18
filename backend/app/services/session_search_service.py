"""Search chat sessions/messages for cross-session references."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import ChatSession, Message

_CROSS_SESSION_RE = re.compile(
    r"\b("
    r"which\s+chat|"
    r"what\s+chat|"
    r"where\s+did\s+we|"
    r"where\s+was\s+(?:it|that|this)|"
    r"which\s+conversation|"
    r"in\s+which\s+chat|"
    r"find\s+(?:the\s+)?chat|"
    r"previous\s+chat|"
    r"other\s+chat|"
    r"another\s+chat|"
    r"talked\s+about|"
    r"discussed\s+(?:this|that|it|blender|unity|python|sql)?|"
    r"conversation\s+(?:about|where)|"
    r"remember\s+when\s+we"
    r")\b",
    re.IGNORECASE,
)

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would could should "
    "i me my we our you your it this that what which where when how why in on at to for of and or "
    "but not with about from into chat conversation session discuss talked said ask asked".split()
)


@dataclass
class SessionSearchHit:
    session_id: str
    session_title: str
    snippet: str
    score: float
    message_role: str = "user"


def detect_cross_session_intent(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_CROSS_SESSION_RE.search(text))


def _extract_keywords(query: str) -> List[str]:
    words = re.findall(r"[a-zA-Z0-9_]{2,}", (query or "").lower())
    keywords = [w for w in words if w not in _STOP_WORDS]
    if not keywords:
        keywords = [w for w in words if len(w) >= 3][:5]
    return keywords[:8]


def _snippet(text: str, keywords: List[str], max_len: int = 160) -> str:
    content = re.sub(r"\s+", " ", (text or "").strip())
    if not content:
        return ""
    lower = content.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(content), idx + max_len - 40)
            excerpt = content[start:end].strip()
            if start > 0:
                excerpt = "…" + excerpt
            if end < len(content):
                excerpt = excerpt + "…"
            return excerpt
    return content[:max_len] + ("…" if len(content) > max_len else "")


def search_sessions(
    db: Session,
    query: str,
    *,
    exclude_session_id: Optional[str] = None,
    limit: int = 5,
    user_id: Optional[str] = None,
) -> List[SessionSearchHit]:
    keywords = _extract_keywords(query)
    if not keywords:
        return []

    like_filters = []
    for kw in keywords:
        pattern = f"%{kw}%"
        like_filters.append(Message.content.ilike(pattern))
        like_filters.append(ChatSession.title.ilike(pattern))

    q = (
        db.query(Message, ChatSession)
        .join(ChatSession, Message.session_id == ChatSession.id)
        .filter(or_(*like_filters))
    )
    if user_id:
        q = q.filter(ChatSession.user_id == user_id)
    if exclude_session_id:
        q = q.filter(ChatSession.id != exclude_session_id)

    rows = q.order_by(Message.created_at.desc()).limit(200).all()

    best: dict[str, SessionSearchHit] = {}
    for msg, session in rows:
        text_blob = f"{session.title} {msg.content}".lower()
        score = 0.0
        for kw in keywords:
            if kw in session.title.lower():
                score += 10.0
            if kw in msg.content.lower():
                score += 3.0
        if score <= 0:
            continue

        existing = best.get(session.id)
        snippet = _snippet(msg.content, keywords)
        if not existing or score > existing.score:
            best[session.id] = SessionSearchHit(
                session_id=session.id,
                session_title=session.title,
                snippet=snippet,
                score=score,
                message_role=msg.role,
            )

    hits = sorted(best.values(), key=lambda h: h.score, reverse=True)
    return hits[:limit]


def is_high_confidence(hits: List[SessionSearchHit], query: str) -> bool:
    if not hits:
        return False
    if detect_cross_session_intent(query):
        return hits[0].score >= 3.0
    return hits[0].score >= 10.0


def format_session_reference_system_message(
    hits: List[SessionSearchHit],
    *,
    explicit_lookup: bool,
) -> str:
    if not hits:
        return ""

    lines = [
        "## Cross-chat context (from other conversations)",
        "The user may be asking about topics discussed in OTHER chats. "
        "Use the matches below — cite the exact chat title and tell the user to open that chat for full context.",
        "",
    ]
    for i, hit in enumerate(hits, 1):
        lines.append(
            f"{i}. Chat **{hit.session_title}** (session_id: `{hit.session_id}`)\n"
            f"   Excerpt ({hit.message_role}): \"{hit.snippet}\""
        )

    if explicit_lookup:
        lines.append(
            "\nThe user asked WHICH CHAT a topic was discussed in. "
            "Lead your answer with the matching chat name(s) from the list above. "
            "Include the excerpt snippet. Tell them to select that chat in the sidebar to continue."
        )
    else:
        lines.append(
            "\nIf your answer relates to a prior discussion listed above, "
            "start with: \"💬 This topic was also discussed in **{chat title}** — open that chat in the sidebar for full context.\""
        )
    return "\n".join(lines)


def format_user_visible_reference(hits: List[SessionSearchHit]) -> str:
    if not hits:
        return ""
    top = hits[0]
    if len(hits) == 1:
        return (
            f"💬 This topic was also discussed in **{top.session_title}** "
            f"— open that chat in the sidebar for full context.\n\n"
        )
    names = ", ".join(f"**{h.session_title}**" for h in hits[:3])
    return f"💬 Related discussions found in: {names} — open those chats for full context.\n\n"


def format_which_chat_direct_answer(hits: List[SessionSearchHit]) -> Optional[str]:
    """Direct answer when user explicitly asks which chat — no LLM needed for clear matches."""
    if not hits:
        return None
    if len(hits) == 1:
        h = hits[0]
        return (
            f"You discussed this in **{h.session_title}**.\n\n"
            f"> {h.snippet}\n\n"
            f"Open **{h.session_title}** from the sidebar to see the full conversation."
        )
    lines = ["I found these matching chats:\n"]
    for h in hits[:5]:
        lines.append(f"- **{h.session_title}** — \"{h.snippet}\"")
    lines.append("\nSelect the chat in the sidebar to view the full conversation.")
    return "\n".join(lines)
