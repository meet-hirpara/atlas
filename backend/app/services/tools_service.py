from typing import List, Optional, Set

from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session

from app.integrations.registry import get_provider
from app.models.bot_settings import BotSettings
from app.models.database import McpServer
from app.services.connection_service import get_all_credentials
from app.services.mcp_service import build_mcp_prompt, build_mcp_tools
from app.services.web_search_tools import (
    build_web_search_prompt,
    build_web_search_tools,
)


def _freelance_tool_names(platform_id: str) -> List[str]:
    return [
        f"{platform_id}_profile_summary",
        f"{platform_id}_search_jobs",
        f"{platform_id}_draft_proposal",
        f"{platform_id}_list_active_gigs",
        f"{platform_id}_draft_follow_up",
    ]


def _mcp_presets_connected(db: Session, user_id: Optional[str] = None) -> Set[str]:
    q = db.query(McpServer).filter(McpServer.enabled == 1)
    if user_id:
        q = q.filter(McpServer.user_id == user_id)
    rows = q.all()
    return {r.preset for r in rows if r.preset}


def build_integrations_prompt(connected: List[str], mcp_presets: Optional[Set[str]] = None) -> str:
    if not connected:
        return ""
    mcp_presets = mcp_presets or set()
    summaries = []
    freelance_platforms: List[tuple] = []
    for pid in connected:
        # Prefer live MCP Upwork over profile-only integration tools
        if pid in mcp_presets:
            continue
        p = get_provider(pid)
        if p:
            summaries.append(f"- **{p.name}**: {p.tool_summary}")
            if p.category == "freelance":
                freelance_platforms.append((pid, p.name))

    if not summaries and not freelance_platforms:
        return ""

    tools_list = "\n".join(summaries)
    freelance_note = ""
    if freelance_platforms:
        platform_lines = []
        for pid, name in freelance_platforms:
            tools = ", ".join(f"`{t}`" for t in _freelance_tool_names(pid))
            platform_lines.append(f"- **{name}** tools: {tools}")
        platform_block = "\n".join(platform_lines)
        freelance_note = f"""
## Freelance assistant mode
The user connected freelance platform(s). Act as their freelance account assistant using profile-linked tools.
{platform_block}

Workflow:
- "Find clients/jobs on Upwork/Fiverr/…" → call `{freelance_platforms[0][0]}_search_jobs` (public web search, NOT live API).
- User pastes a job post → call `{freelance_platforms[0][0]}_draft_proposal` with title + description.
- "What's my profile?" / "summarize my Upwork" → `{freelance_platforms[0][0]}_profile_summary`.
- Active projects → `{freelance_platforms[0][0]}_list_active_gigs` (manually tracked in settings).
- Follow-up messages → `{freelance_platforms[0][0]}_draft_follow_up`.

Rules:
- Be proactive: after connecting, offer job search and proposal help.
- NEVER claim live API access, synced messages, or auto-submitted proposals.
- If search returns few results, suggest pasting a job URL/description for a proposal draft.
- Pick the tool matching the platform the user named; if only one freelance platform is connected, use it by default.
"""
    return f"""
## Connected integrations
The user has connected these services. Use the available tools to act on their behalf:
{tools_list}
{freelance_note}
Rules:
- Use the correct tool when asked to send messages, emails, create issues, search data, etc.
- After using a tool, summarize what you did clearly.
- If a service is not connected, tell the user to connect it in Settings → Integrations.
- Ask for missing details (recipient, channel, project ID) before acting when unclear.
- For database tools, only run read-only queries unless explicitly asked to write via the service's create tools.
"""


def build_integration_tools(
    db: Session,
    bot_settings: Optional[BotSettings] = None,
    user_message: str = "",
    sources_collector: Optional[list] = None,
    user_id: Optional[str] = None,
) -> List[StructuredTool]:
    creds_map = get_all_credentials(db, user_id=user_id)
    tools: List[StructuredTool] = []
    mcp_presets = _mcp_presets_connected(db, user_id=user_id)

    for provider_id, creds in creds_map.items():
        # Skip freelance/integration tools that collide with a live MCP preset
        if provider_id in mcp_presets:
            continue
        provider = get_provider(provider_id)
        if not provider:
            continue
        try:
            tools.extend(provider.build_tools(creds))
        except Exception:
            continue

    try:
        tools.extend(build_mcp_tools(db, user_id=user_id))
    except Exception:
        pass

    try:
        tools.extend(build_web_search_tools(bot_settings, user_message, sources_collector))
    except Exception:
        pass

    # Deduplicate by tool name (last writer wins, but prefer mcp_* already added last)
    deduped: dict = {}
    for t in tools:
        deduped[t.name] = t
    return list(deduped.values())


def get_integrations_prompt(
    db: Session,
    bot_settings: Optional[BotSettings] = None,
    user_id: Optional[str] = None,
) -> str:
    creds_map = get_all_credentials(db, user_id=user_id)
    mcp_presets = _mcp_presets_connected(db, user_id=user_id)
    parts = [
        build_integrations_prompt(list(creds_map.keys()), mcp_presets),
        build_mcp_prompt(db, user_id=user_id),
    ]
    if bot_settings and bot_settings.web_search_mode != "off":
        parts.append(build_web_search_prompt())
    return "".join(p for p in parts if p)
