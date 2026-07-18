import json
import logging
from typing import AsyncGenerator, List, Optional

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from sqlalchemy.orm import Session

from app.models.bot_settings import BotSettings
from app.services.llm_service import get_llm
from app.services.tools_service import build_integration_tools, get_integrations_prompt

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8


async def run_with_tools(
    db: Session,
    messages: List,
    bot_settings: Optional[BotSettings],
    model_id: Optional[str] = None,
    user_message: str = "",
    sources_collector: Optional[list] = None,
    user_id: Optional[str] = None,
) -> tuple[str, bool]:
    """Run tool-calling loop. Returns (final_text, used_tools)."""
    tools = build_integration_tools(
        db, bot_settings, user_message, sources_collector, user_id=user_id
    )
    if not tools:
        return "", False

    llm = get_llm(streaming=False, bot_settings=bot_settings, model_id=model_id).bind_tools(tools)
    tool_map = {t.name: t for t in tools}
    working = list(messages)

    integrations_prompt = get_integrations_prompt(db, bot_settings, user_id=user_id)
    if working and isinstance(working[0], SystemMessage) and integrations_prompt:
        working[0] = SystemMessage(content=working[0].content + integrations_prompt)

    used_tools = False
    for _ in range(MAX_TOOL_ROUNDS):
        response: AIMessage = await llm.ainvoke(working)
        working.append(response)

        if not response.tool_calls:
            text = response.content if isinstance(response.content, str) else str(response.content)
            return text, used_tools

        used_tools = True
        for tc in response.tool_calls:
            name = tc["name"]
            args = tc["args"]
            tool = tool_map.get(name)
            try:
                result = tool.invoke(args) if tool else f"Unknown tool: {name}"
            except Exception as e:
                logger.exception("Tool invocation failed name=%s args_keys=%s", name, list(args.keys()) if isinstance(args, dict) else type(args))
                result = f"Tool error: {e}"
            working.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    last = working[-1]
    if isinstance(last, AIMessage):
        return last.content if isinstance(last.content, str) else str(last.content), used_tools
    return "I completed the requested actions.", used_tools


async def stream_text(text: str) -> AsyncGenerator[str, None]:
    """Yield pre-generated text as SSE tokens (chunked for smooth UI)."""
    chunk_size = 4
    for i in range(0, len(text), chunk_size):
        yield f"data: {json.dumps({'token': text[i:i + chunk_size]})}\n\n"
