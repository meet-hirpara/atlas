"""Session-scoped ephemeral specialist agents — create, use, dismiss."""

import json
import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.database import SessionAgent

CREATE_PATTERNS = [
    re.compile(r"\bact as (?:a |an )?(.+?)(?:\.|,|$| for\b)", re.IGNORECASE),
    re.compile(r"\bbe my (.+?) expert\b", re.IGNORECASE),
    re.compile(r"\bcreate (?:an? )?(.+?) agent\b", re.IGNORECASE),
    re.compile(r"\bbuild (?:me )?(?:a |an )?(.+?) agent\b", re.IGNORECASE),
    re.compile(r"\bhelp me (?:debug|with) (.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"\bspecialist (?:for|in) (.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"\b(?:switch to|enable) (.+?) (?:mode|agent)\b", re.IGNORECASE),
]

DISMISS_PATTERNS = [
    re.compile(r"\b(dismiss|remove|deactivate|delete) (?:the )?(?:ephemeral )?agent\b", re.IGNORECASE),
    re.compile(r"\bgo back to (?:normal|default)\b", re.IGNORECASE),
    re.compile(r"\bexit (?:agent|specialist) mode\b", re.IGNORECASE),
]

ROLE_PROMPT_TEMPLATE = """## Ephemeral specialist agent: {name}
You are operating as **{name}** for this conversation until the user dismisses this agent.

### Role
{description}

### Guidelines
- Stay in character and apply deep domain expertise for {domain}.
- Use available tools and integrations when they help solve the user's problem.
- If the request falls outside your specialty, say so and suggest dismissing this agent.
"""

DOMAIN_HINTS = {
    "sql": "Write correct, efficient SQL. Explain query plans when relevant. Prefer parameterized queries.",
    "api": "Focus on REST/HTTP design, status codes, auth, validation, and debugging request/response flows.",
    "python": "Follow PEP 8, use type hints, and provide idiomatic Python solutions.",
    "javascript": "Use modern ES modules, clear async patterns, and framework-appropriate conventions.",
    "typescript": "Prefer strict typing, clear interfaces, and maintainable TS patterns.",
    "react": "Use hooks, component composition, and accessible UI patterns.",
    "debug": "Work systematically: reproduce, isolate, hypothesize, verify, and propose minimal fixes.",
    "security": "Apply OWASP-minded review: injection, auth, secrets, input validation, least privilege.",
    "devops": "Cover CI/CD, containers, infra-as-code, observability, and deployment safety.",
}


def detect_create_intent(message: str) -> Optional[str]:
    text = (message or "").strip()
    if not text:
        return None
    for pattern in CREATE_PATTERNS:
        m = pattern.search(text)
        if m:
            hint = m.group(1).strip().rstrip(".")
            if len(hint) >= 2:
                return hint
    return None


def detect_dismiss_intent(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return any(p.search(text) for p in DISMISS_PATTERNS)


def _title_case_role(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw.strip().rstrip("."))
    if len(cleaned) > 60:
        cleaned = cleaned[:60].rsplit(" ", 1)[0]
    if not cleaned:
        return "Specialist"
    return cleaned[0].upper() + cleaned[1:]


def _display_name(role_hint: str) -> str:
    name = _title_case_role(role_hint)
    lower = name.lower()
    if "expert" in lower or "specialist" in lower or "agent" in lower:
        return name
    if len(name.split()) <= 3:
        return f"{name} Expert"
    return name


def _domain_description(domain: str, user_message: str) -> str:
    lower = domain.lower()
    for key, hint in DOMAIN_HINTS.items():
        if key in lower:
            return (
                f"You are a specialist focused on **{domain}**. {hint} "
                f"The user asked: \"{user_message.strip()[:200]}\""
            )
    return (
        f"You are a specialist focused on **{domain}**. "
        f"Apply expert-level knowledge to the user's requests in this area. "
        f"Context: \"{user_message.strip()[:200]}\""
    )


def _infer_model(domain: str) -> str:
    lower = domain.lower()
    code_terms = ("python", "javascript", "typescript", "react", "code", "debug", "api", "sql")
    if any(t in lower for t in code_terms):
        return "codestral-latest"
    return ""


def generate_agent_config(role_hint: str, user_message: str) -> dict:
    display_name = _display_name(role_hint)
    domain = role_hint.strip()
    description = _domain_description(domain, user_message)
    return {
        "name": display_name,
        "role_prompt": ROLE_PROMPT_TEMPLATE.format(
            name=display_name,
            description=description,
            domain=domain,
        ),
        "model_preference": _infer_model(domain),
        "allowed_tools": json.dumps(["all"]),
    }


def agent_to_dict(agent: SessionAgent) -> dict:
    return {
        "id": agent.id,
        "session_id": agent.session_id,
        "name": agent.name,
        "role_prompt": agent.role_prompt,
        "model_preference": agent.model_preference or "",
        "allowed_tools": json.loads(agent.allowed_tools or '["all"]'),
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


def get_active_agent(db: Session, session_id: str) -> Optional[SessionAgent]:
    return (
        db.query(SessionAgent)
        .filter(SessionAgent.session_id == session_id)
        .order_by(SessionAgent.created_at.desc())
        .first()
    )


def dismiss_active_agent(db: Session, session_id: str, agent_id: Optional[str] = None) -> Optional[SessionAgent]:
    query = db.query(SessionAgent).filter(SessionAgent.session_id == session_id)
    if agent_id:
        agent = query.filter(SessionAgent.id == agent_id).first()
    else:
        agent = query.order_by(SessionAgent.created_at.desc()).first()
    if not agent:
        return None
    db.delete(agent)
    db.commit()
    return agent


def create_agent_from_message(db: Session, session_id: str, role_hint: str, user_message: str) -> SessionAgent:
    dismiss_active_agent(db, session_id)
    config = generate_agent_config(role_hint, user_message)
    agent = SessionAgent(
        id=str(uuid.uuid4()),
        session_id=session_id,
        name=config["name"],
        role_prompt=config["role_prompt"],
        model_preference=config["model_preference"],
        allowed_tools=config["allowed_tools"],
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def create_agent_manual(db: Session, session_id: str, name: str, role_prompt: str, model_preference: str = "") -> SessionAgent:
    dismiss_active_agent(db, session_id)
    agent = SessionAgent(
        id=str(uuid.uuid4()),
        session_id=session_id,
        name=name,
        role_prompt=role_prompt,
        model_preference=model_preference or "",
        allowed_tools=json.dumps(["all"]),
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent
