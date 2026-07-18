"""Ground-truth app help knowledge derived from the codebase — no hallucinated steps."""

from __future__ import annotations

import re
from typing import List, Optional

from app.integrations.registry import list_provider_catalog
from app.services.mcp_service import MCP_PRESETS

_APP_HELP_RE = re.compile(
    r"\b("
    r"how\s+(?:do\s+i|to|can\s+i)|"
    r"where\s+(?:is|are|do\s+i)|"
    r"what\s+(?:is|are)\s+(?:the\s+)?(?:setting|feature|option)|"
    r"help\s+(?:me\s+)?(?:with|connect|setup|set\s+up)|"
    r"(?:connect|setup|set\s+up|install|enable|configure|use)\s+(?:blender|unity|mcp|github|web\s+search|deep\s+research|pdf|document|integration|ephemeral|agent|rename)|"
    r"(?:blender|unity|mcp|github|web\s+search|deep\s+research|settings?|integrations?)\s+(?:help|setup|connect|how)|"
    r"what\s+(?:does|can)\s+(?:this|nexus|the\s+app|the\s+bot)|"
    r"how\s+(?:does|do)\s+(?:i|you|this|nexus|the\s+app|the\s+bot)|"
    r"(?:do\s+i|need\s+to|should\s+i)\s+(?:install|download)|"
    r"(?:will|does)\s+(?:this|it|that)\s+work|"
    r"(?:is\s+that|just)\s+(?:enough|correct|all)|"
    r"to\s+connect\s+blender|"
    r"connect\s+blender"
    r")\b",
    re.IGNORECASE,
)

# Blender/MCP questions even without explicit "how to" (e.g. "install blender and click connect?")
_BLENDER_CONNECT_RE = re.compile(
    r"\b(?:blender|mcp\s*&?\s*3d)\b.*\b(?:connect|install|click|work|addon|server)\b|"
    r"\b(?:connect|install|click)\b.*\b(?:blender|mcp)\b",
    re.IGNORECASE,
)

_BLENDER_RE = re.compile(r"\bblender\b", re.IGNORECASE)
_UNITY_RE = re.compile(r"\bunity\b", re.IGNORECASE)
_MCP_RE = re.compile(r"\bmcp\b", re.IGNORECASE)
_GITHUB_RE = re.compile(r"\bgithub\b", re.IGNORECASE)
_WEB_SEARCH_RE = re.compile(r"\bweb\s+search\b", re.IGNORECASE)
_DEEP_RESEARCH_RE = re.compile(r"\bdeep\s+research\b", re.IGNORECASE)
_EPHEMERAL_RE = re.compile(r"\bephemeral\s+agent\b|\bact\s+as\b|\bspecialist\s+agent\b", re.IGNORECASE)
_DOCUMENT_RE = re.compile(r"\b(?:pdf|document|upload)\b", re.IGNORECASE)
_RENAME_RE = re.compile(r"\brename\s+(?:chat|conversation|session)\b", re.IGNORECASE)


def detect_app_help_intent(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if _APP_HELP_RE.search(text):
        return True
    return bool(_BLENDER_CONNECT_RE.search(text))


def _settings_overview() -> str:
    return """## Settings (gear icon in sidebar → Settings)

Tabs and what they control:
- **Chat** — AI model (Auto or specific Mistral model), OCR model for PDFs, personality, response length, creativity, diagram mode (auto / on request / off), code style, clarifying questions toggle, custom instructions.
- **Integrations** — Connect third-party apps (Slack, Gmail, GitHub, Jira, etc.) with API credentials. Connected integrations expose tools the AI can call in chat.
- **MCP & 3D** — Connect Blender, Unity, or custom MCP servers so the AI can control 3D editors from chat.
- **GitHub Repos** — Add repository URLs to index code; toggle repos active per chat for code-aware answers and build mode.

Changes in Settings save automatically to your browser (localStorage)."""


def _web_search_help() -> str:
    return """## Web search
- Toggle the **globe icon** in the chat composer to turn web search on or off for normal messages.
- Setting `webSearchMode` in bot settings: `on` (default) or `off`. When on, the AI searches the web for current facts when relevant.
- Backend uses Tavily if `TAVILY_API_KEY` is set in `backend/.env`; otherwise falls back to another provider.
- **Deep research** (telescope icon in composer) always uses the web — multi-step research with sources."""


def _deep_research_help() -> str:
    return """## Deep research
- Click the **telescope (Deep research)** option in the chat composer menu (+ button) before sending.
- Runs a multi-phase pipeline: planning → web searching → analyzing sources → writing a report with citations.
- Internet is always on during deep research regardless of the globe toggle."""


def _documents_help() -> str:
    return """## PDF & documents
- Use the **+** menu in the chat composer → attach PDF files to the current chat.
- Documents are processed per chat session; answers cite uploaded PDFs with [1], [2] style references.
- OCR model is configured in Settings → Chat → PDF & documents."""


def _github_help() -> str:
    return """## GitHub repos
- Open Settings → **GitHub Repos** → paste a repo URL (optional token for private repos) → Add.
- Wait until status is **ready** (indexed). Toggle repos **active** to include them in chat context.
- Active repos supply code excerpts for Q&A and production **build mode** when you ask to create/build projects."""


def _ephemeral_agents_help() -> str:
    return """## Ephemeral agents (per-chat specialists)
- Say e.g. "act as a SQL expert" or "create a Python debugging agent" to spawn a session-scoped specialist.
- The agent chip appears above the chat; it changes the AI's role until dismissed.
- Dismiss with "dismiss agent", "go back to normal", or the × on the agent chip.
- One active ephemeral agent per chat at a time."""


def _rename_chat_help() -> str:
    return """## Rename a chat
- In the sidebar, **double-click** a chat title or click the **pencil icon** on hover.
- Type the new name and press Enter (Escape to cancel).
- Renaming saves immediately via the sessions API."""


def _blender_help() -> str:
    preset = MCP_PRESETS["blender"]
    sse = MCP_PRESETS["blender_sse"]
    stdio_cmd = f"{preset['command']} {' '.join(preset['args'])}".strip()
    steps = preset["setup_steps"]
    sse_steps = sse["setup_steps"]
    return f"""## Connect Blender (exact steps)

Flow: **Blender addon → Start Server → Settings → MCP → Connect Blender → `{stdio_cmd}`**

### Prerequisites
1. **Blender** installed and running.
2. **Blender MCP addon** installed (from the addon's GitHub releases).
3. In Blender: press **N** → **MCP** tab → click **Start Server**.
4. **uv** installed for the bridge: `pip install uv`

### Recommended — stdio (Settings → MCP & 3D → Connect Blender)
1. Open **Settings** (gear in sidebar) → **MCP & 3D** tab.
2. Ensure Blender MCP server is running (step 3 above).
3. Click **Connect Blender** (Recommended · stdio). Atlas runs `{stdio_cmd}` automatically — you do not run it manually.
4. On success, Blender tools appear in chat. Try: "Create a red cube in Blender at the origin."

Setup steps from app preset:
{chr(10).join(f"- {s}" for s in steps)}

### Alternative — HTTP/SSE
1. Enable HTTP/SSE in the Blender MCP addon panel.
2. Copy the URL from Blender (default: `{sse['url']}`).
3. In Settings → MCP & 3D, choose **Direct HTTP · SSE**, paste URL, click Connect.

{chr(10).join(f"- {s}" for s in sse_steps)}

### Troubleshooting
- Connection failed → confirm Blender is open and **Start Server** was clicked in the MCP panel.
- Tools not showing → Settings → MCP & 3D → Test connection on your Blender server entry.

### FAQ — "Can I just install Blender and click Connect?"
**No.** Clicking Connect alone is not enough. You must also:
1. Install the **Blender MCP addon** inside Blender (Connect does not install this for you).
2. Open Blender and click **Start Server** in the MCP panel (N key) **before** connecting in this app.
3. Install **uv** on your system (`pip install uv`) for the recommended stdio bridge.

Without the addon + running server, Connect will fail or show disconnected."""


def _unity_help() -> str:
    lines = []
    for key in ("unity", "unity_stdio"):
        p = MCP_PRESETS[key]
        transport = p["transport"]
        detail = p["url"] if transport == "sse" else f"{p['command']} {' '.join(p['args'])}".strip()
        lines.append(f"### {p['name']} ({transport})")
        lines.append(f"Default: {detail}")
        for i, step in enumerate(p["setup_steps"], 1):
            lines.append(f"{i}. {step}")
        lines.append("")
    return "## Connect Unity\n" + "\n".join(lines) + "\nConnect via Settings → MCP & 3D → Other apps & custom servers → Unity."


def _mcp_general_help() -> str:
    custom = MCP_PRESETS["custom"]
    return f"""## MCP (Model Context Protocol)
- Settings → **MCP & 3D** tab connects external apps via MCP tools.
- Presets: Blender (stdio `{MCP_PRESETS['blender']['command']} {' '.join(MCP_PRESETS['blender']['args'])}`), Blender SSE, Unity, Unity stdio bridge, Custom.
- After connecting, enabled servers expose tools in chat (prefixed with server name).
- Custom server steps:
{chr(10).join(f"- {s}" for s in custom['setup_steps'])}"""


def _integrations_help() -> str:
    providers = list_provider_catalog()
    by_cat: dict = {}
    for p in providers:
        cat = p.get("category_label") or p.get("category", "Other")
        by_cat.setdefault(cat, []).append(p["name"])
    lines = ["## Integrations (Settings → Integrations tab)", "Connect apps with API credentials; the AI uses them as tools in chat.", ""]
    for cat, names in sorted(by_cat.items()):
        lines.append(f"**{cat}**: {', '.join(names)}")
    lines.append("")
    lines.append("To connect: Settings → Integrations → expand a provider → enter credentials → Connect.")
    return "\n".join(lines)


def build_app_knowledge(message: str) -> str:
    """Return relevant APP_KNOWLEDGE sections for the user message."""
    sections: List[str] = [
        "# APP KNOWLEDGE (authoritative — follow exactly, do not invent steps)",
        "You are answering about **this chat application** (Atlas). "
        "Use ONLY the information below. If something is not listed, say you don't know rather than guessing.",
        _settings_overview(),
    ]

    text = message or ""
    specific = any(
        r.search(text)
        for r in (
            _BLENDER_RE,
            _UNITY_RE,
            _MCP_RE,
            _GITHUB_RE,
            _WEB_SEARCH_RE,
            _DEEP_RESEARCH_RE,
            _EPHEMERAL_RE,
            _DOCUMENT_RE,
            _RENAME_RE,
        )
    )

    if _BLENDER_RE.search(text) or (not specific and _MCP_RE.search(text)):
        sections.append(_blender_help())
    if _UNITY_RE.search(text):
        sections.append(_unity_help())
    if _MCP_RE.search(text) and not _BLENDER_RE.search(text) and not _UNITY_RE.search(text):
        sections.append(_mcp_general_help())
    if _GITHUB_RE.search(text):
        sections.append(_github_help())
    if _WEB_SEARCH_RE.search(text):
        sections.append(_web_search_help())
    if _DEEP_RESEARCH_RE.search(text):
        sections.append(_deep_research_help())
    if _DOCUMENT_RE.search(text):
        sections.append(_documents_help())
    if _EPHEMERAL_RE.search(text):
        sections.append(_ephemeral_agents_help())
    if _RENAME_RE.search(text):
        sections.append(_rename_chat_help())

    if not specific:
        sections.extend([
            _web_search_help(),
            _deep_research_help(),
            _documents_help(),
            _github_help(),
            _ephemeral_agents_help(),
            _rename_chat_help(),
            _mcp_general_help(),
            _integrations_help(),
        ])

    if _GITHUB_RE.search(text) or "integration" in text.lower():
        sections.append(_integrations_help())

    return "\n\n".join(sections)


def format_app_knowledge_system_message(message: str) -> Optional[str]:
    if not detect_app_help_intent(message):
        return None
    return build_app_knowledge(message)
