import json
from typing import AsyncGenerator, List, Optional, Tuple

from langchain_core.messages import HumanMessage

from app.models.bot_settings import BotSettings
from app.services.llm_service import get_llm
from app.services.model_router import build_routing_plan
from app.services.model_service import fetch_mistral_models


async def run_orchestrated(
    lc_messages: list,
    user_message: str,
    bot_settings: Optional[BotSettings],
    model_selection: str = "auto",
) -> Tuple[str, str]:
    """
    Returns (final_response, routing_explanation).
  Fugu-inspired: Thinker plans → Workers execute → Synthesizer merges.
    """
    models = await fetch_mistral_models()
    plan = build_routing_plan(user_message, models, model_selection)

    if plan.mode == "single":
        llm = get_llm(streaming=False, bot_settings=bot_settings, model_id=plan.primary_model)
        response = await llm.ainvoke(lc_messages)
        text = response.content if isinstance(response.content, str) else str(response.content)
        return text, plan.explanation

    # Multi-model orchestration
    worker_outputs: List[str] = []
    thinker_outline = ""

    for task in plan.subtasks:
        if task.role == "thinker":
            llm = get_llm(streaming=False, bot_settings=bot_settings, model_id=task.model_id, temperature=0.3)
            resp = await llm.ainvoke([HumanMessage(content=task.prompt)])
            thinker_outline = resp.content if isinstance(resp.content, str) else str(resp.content)
            worker_outputs.append(f"## Plan (Thinker — {task.model_id})\n{thinker_outline}")
            continue

        if task.role == "worker":
            llm = get_llm(streaming=False, bot_settings=bot_settings, model_id=task.model_id)
            context = f"Planning context:\n{thinker_outline}\n\n" if thinker_outline else ""
            resp = await llm.ainvoke([HumanMessage(content=context + task.prompt)])
            content = resp.content if isinstance(resp.content, str) else str(resp.content)
            worker_outputs.append(f"## {task.task_type.title()} Specialist ({task.model_id})\n{content}")

    synth_task = next((t for t in plan.subtasks if t.role == "synthesizer"), None)
    if not synth_task:
        return "\n\n".join(worker_outputs), plan.explanation

    synthesis_prompt = (
        "You are the Synthesizer in a multi-model AI system (inspired by Sakana Fugu / Trinity architecture). "
        "Multiple specialist models have contributed partial answers. Merge them into ONE coherent, "
        "well-structured final response for the user. Remove redundancy. Cite which specialist handled what "
        "only if helpful. Do not mention internal architecture unless asked.\n\n"
    )
    if bot_settings and bot_settings.response_length == "detailed":
        synthesis_prompt += (
            "IMPORTANT: The user chose **Detailed** response length. Preserve and combine ALL substantive "
            "content from specialists — do NOT compress into a short summary. The final answer must be "
            "long-form with multiple `##` sections and 800+ words when the topic warrants depth.\n\n"
        )
    synthesis_prompt += (
        f"## Original user request\n{user_message}\n\n"
        f"## Specialist contributions\n" + "\n\n---\n\n".join(worker_outputs)
    )

    llm = get_llm(streaming=False, bot_settings=bot_settings, model_id=synth_task.model_id)
    resp = await llm.ainvoke([HumanMessage(content=synthesis_prompt)])
    final = resp.content if isinstance(resp.content, str) else str(resp.content)
    return final, plan.explanation


async def stream_orchestrated(
    lc_messages: list,
    user_message: str,
    bot_settings: Optional[BotSettings],
    model_selection: str = "auto",
) -> AsyncGenerator[str, None]:
    """Yield SSE events including routing meta then streamed or chunked response."""
    models = await fetch_mistral_models()
    plan = build_routing_plan(user_message, models, model_selection)

    yield f"data: {json.dumps({'meta': plan.explanation})}\n\n"

    if plan.mode == "single":
        llm = get_llm(streaming=True, bot_settings=bot_settings, model_id=plan.primary_model)
        async for chunk in llm.astream(lc_messages):
            token = chunk.content
            if token:
                yield f"data: {json.dumps({'token': token})}\n\n"
        return

    yield f"data: {json.dumps({'activity': {'phase': 'reasoning', 'label': 'Reasoning', 'detail': 'Coordinating specialist models'}})}\n\n"
    yield f"data: {json.dumps({'meta': 'Orchestrating multiple specialist models…'})}\n\n"
    text, _ = await run_orchestrated(lc_messages, user_message, bot_settings, model_selection)

    yield f"data: {json.dumps({'activity': {'phase': 'writing', 'label': 'Writing', 'detail': 'Composing response'}})}\n\n"

    chunk_size = 6
    for i in range(0, len(text), chunk_size):
        yield f"data: {json.dumps({'token': text[i:i + chunk_size]})}\n\n"
