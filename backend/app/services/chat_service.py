import json
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, List, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import ChatSession, Message
from app.models.bot_settings import BotSettings
from app.services.memory_service import memory_service
from app.services.document_service import document_service
from app.services.github_repo_service import github_repo_service
from app.services.build_mode_service import is_build_request, BUILD_MODE_META
from app.services.prompt_builder import build_system_prompt
from app.services.orchestrator_service import stream_orchestrated
from app.services.model_router import build_routing_plan
from app.services.model_service import fetch_mistral_models
from app.services.web_search_tools import should_prefetch_web
from app.services.web_search_service import encode_sources_message, merge_sources, search_and_format
from app.services.agent_service import run_with_tools, stream_text
from app.services.tools_service import build_integration_tools
from app.services.deep_research_service import stream_deep_research
from app.services.clarification_service import (
    check_clarification_needed,
    clarification_event,
    encode_clarification_message,
    is_clarification_content,
    is_complex_query,
    parse_clarification,
)
from app.services.ephemeral_agent_service import (
    detect_create_intent,
    detect_dismiss_intent,
    get_active_agent,
    create_agent_from_message,
    dismiss_active_agent,
    agent_to_dict,
)
from app.services.youtube_service import (
    detect_video_intent,
    encode_youtube_message,
    search_youtube,
    youtube_event,
)
from app.services.app_knowledge_service import format_app_knowledge_system_message
from app.services.model_display_service import (
    encode_model_message,
    resolve_model_display,
    strip_model_message,
)
from app.services.session_search_service import (
    detect_cross_session_intent,
    format_session_reference_system_message,
    format_user_visible_reference,
    format_which_chat_direct_answer,
    is_high_confidence,
    search_sessions,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def _activity_event(phase: str, label: str = "", detail: str = "") -> str:
    payload: dict = {"phase": phase}
    if label:
        payload["label"] = label
    if detail:
        payload["detail"] = detail
    return f"data: {json.dumps({'activity': payload})}\n\n"


def create_session(db: Session, title: str = "New Chat", user_id: str | None = None) -> ChatSession:
    session = ChatSession(
        id=str(uuid.uuid4()),
        title=title,
        user_id=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def append_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    sources: str = "",
) -> Optional[Message]:
    """Persist a single message without invoking the LLM (connect cards, stream errors)."""
    session = get_session(db, session_id)
    if not session:
        return None
    msg = Message(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        sources=sources or "",
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    session.updated_at = datetime.utcnow()
    # Keep title useful for connect flows
    if role == "user" and (not session.title or session.title == "New Chat"):
        session.title = (content[:60] + "…") if len(content) > 60 else content
    db.commit()
    db.refresh(msg)
    _mirror_message_to_cache(msg)
    return msg


def get_sessions(db: Session, user_id: str | None = None) -> List[ChatSession]:
    from app.services.workspace_service import get_sessions_ordered
    return get_sessions_ordered(db, user_id=user_id)


def get_session(db: Session, session_id: str) -> Optional[ChatSession]:
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_messages(db: Session, session_id: str) -> List[Message]:
    primary = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    cached = _messages_from_cache(session_id)
    if cached is None:
        return primary
    # Prefer whichever store has the fuller history (covers pre-Redis messages)
    return cached if len(cached) >= len(primary) else primary


def delete_session(db: Session, session_id: str) -> bool:
    session = get_session(db, session_id)
    if not session:
        return False
    db.delete(session)
    db.commit()
    _delete_cache_session(session_id)
    return True


def _mirror_message_to_cache(msg: Message) -> None:
    try:
        from app.storage.manager import get_storage_manager

        hist = get_storage_manager().redis_chat
        if hist:
            hist.append(msg)
    except Exception as exc:
        logger.warning("Redis chat mirror failed: %s", exc)


def _messages_from_cache(session_id: str) -> Optional[List[Message]]:
    try:
        from app.storage.manager import get_storage_manager

        hist = get_storage_manager().redis_chat
        if not hist:
            return None
        return hist.list_messages(session_id)
    except Exception as exc:
        logger.warning("Redis chat read failed: %s", exc)
        return None


def _delete_cache_session(session_id: str) -> None:
    try:
        from app.storage.manager import get_storage_manager

        hist = get_storage_manager().redis_chat
        if hist:
            hist.delete_session(session_id)
    except Exception as exc:
        logger.warning("Redis chat delete failed: %s", exc)


def update_session_title(db: Session, session_id: str, title: str) -> Optional[ChatSession]:
    session = get_session(db, session_id)
    if not session:
        return None
    session.title = title
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def _retrieve_doc_hits(db: Session, session_id: str, user_message: str) -> List[dict]:
    if not document_service.session_has_ready_docs(db, session_id):
        return []
    doc_count = document_service.ready_doc_count(db, session_id)
    k = min(24, settings.doc_retrieval_k + doc_count // 4)
    return document_service.search(db, session_id, user_message, k=k)


def _build_langchain_messages(
    db: Session, session_id: str, user_message: str, bot_settings: Optional[BotSettings] = None,
    doc_hits: Optional[List[dict]] = None,
    app_knowledge: Optional[str] = None,
    cross_session_context: Optional[str] = None,
) -> list:
    build_mode = is_build_request(user_message)
    messages = [SystemMessage(content=build_system_prompt(bot_settings, build_mode=build_mode, user_message=user_message))]

    if app_knowledge:
        messages.append(
            SystemMessage(
                content=(
                    app_knowledge
                    + "\n\nAnswer using ONLY the APP KNOWLEDGE above for app/settings/how-to questions. "
                    "Do not invent steps, URLs, or UI locations not listed. "
                    "If the user asks whether a simplified flow (e.g. 'just install and click Connect') is enough, "
                    "clearly say no when prerequisites are missing and list every required step from APP KNOWLEDGE."
                )
            )
        )

    if cross_session_context:
        messages.append(SystemMessage(content=cross_session_context))

    if doc_hits is None:
        doc_hits = _retrieve_doc_hits(db, session_id, user_message)

    if doc_hits:
        blocks = []
        for i, hit in enumerate(doc_hits, 1):
            page = hit.get("page_start", 1)
            page_end = hit.get("page_end", page)
            page_ref = f"p.{page}" if page == page_end else f"pp.{page}–{page_end}"
            blocks.append(
                f"[{i}] {hit['filename']} ({page_ref})\n{hit['content']}"
            )
        messages.append(
            SystemMessage(
                content=(
                    "The user has uploaded PDF documents in this chat. "
                    "Answer using the numbered excerpts below. "
                    "When you use information from an excerpt, cite it inline using [1], [2], etc. "
                    "matching the excerpt numbers. Place citations immediately after the relevant claim. "
                    "If the answer is not in the excerpts, say so clearly.\n\n"
                    + "\n\n---\n\n".join(blocks)
                )
            )
        )
    elif document_service.session_has_removed_docs(db, session_id):
        messages.append(
            SystemMessage(
                content=(
                    "No PDF documents are currently attached to this chat. "
                    "The user removed previously uploaded files. "
                    "Do not use content from those removed documents to answer new questions, "
                    "even if earlier messages in this conversation discussed them."
                )
            )
        )

    active_repo_ids = bot_settings.active_github_repo_ids if bot_settings else []
    if active_repo_ids:
        hits, is_relevant, repo_names = github_repo_service.get_relevant_context(
            db, active_repo_ids, user_message
        )
        is_build = build_mode
        if is_relevant and hits:
            blocks = []
            for hit in hits:
                blocks.append(
                    f"[{hit['owner']}/{hit['repo_name']} | {hit['file_path']} | chunk {hit['chunk_index']}]\n{hit['content']}"
                )
            ref_note = ", ".join(repo_names)
            build_hint = (
                " Use this indexed repository as a reference for patterns, structure, and APIs when generating code."
                if is_build
                else ""
            )
            messages.append(
                SystemMessage(
                    content=(
                        f"Using indexed GitHub repo(s) as reference: {ref_note}.{build_hint}\n"
                        "Answer using the code excerpts below. Cite file paths when relevant.\n\n"
                        + "\n\n---\n\n".join(blocks)
                    )
                )
            )
        elif is_build and active_repo_ids:
            ready = [
                r for r in github_repo_service.list_repos(db)
                if r.id in active_repo_ids and r.status == "ready"
            ]
            if ready:
                names = [f"{r.owner}/{r.name}" for r in ready]
                messages.append(
                    SystemMessage(
                        content=(
                            f"The user asked to build or create something, but their indexed repos "
                            f"({', '.join(names)}) don't appear relevant to this request. "
                            "Do NOT force-fit code from those repos. Instead, suggest a better approach "
                            "(e.g. web search, a different stack, or adding a more relevant repo). "
                            "You may still answer generally without repo context."
                        )
                    )
                )

    recalled = memory_service.recall_relevant(session_id, user_message)
    if recalled:
        context = "\n---\n".join(recalled)
        messages.append(
            SystemMessage(
                content=f"Relevant context from earlier in this conversation:\n{context}"
            )
        )

    active_agent = get_active_agent(db, session_id)
    if active_agent:
        messages.append(SystemMessage(content=active_agent.role_prompt))

    history = get_messages(db, session_id)
    for msg in history[-20:]:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            content = msg.content
            if is_clarification_content(content):
                parsed = parse_clarification(content)
                content = parsed["question"] if parsed else content
            content = strip_model_message(content)
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_message))
    return messages


def _generate_title(user_message: str) -> str:
    title = user_message.strip()[:50]
    if len(user_message) > 50:
        title += "..."
    return title or "New Chat"


async def stream_chat(
    db: Session,
    session_id: str,
    user_message: str,
    bot_settings: Optional[BotSettings] = None,
    deep_research: bool = False,
) -> AsyncGenerator[str, None]:
    session = get_session(db, session_id)
    if not session:
        yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
        return

    user_msg = Message(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=user_message,
        created_at=datetime.utcnow(),
    )
    db.add(user_msg)

    if session.title == "New Chat":
        session.title = _generate_title(user_message)
    session.updated_at = datetime.utcnow()
    db.commit()
    _mirror_message_to_cache(user_msg)

    model_selection = bot_settings.model_selection if bot_settings else "mistral-large"
    model_display_name = resolve_model_display(model_id=model_selection)
    yield f"data: {json.dumps({'model_display': model_display_name})}\n\n"

    if detect_dismiss_intent(user_message):
        dismissed = dismiss_active_agent(db, session_id)
        if dismissed:
            yield f"data: {json.dumps({'ephemeral_agent': {'action': 'dismissed', 'name': dismissed.name}})}\n\n"

    create_hint = detect_create_intent(user_message)
    if create_hint:
        new_agent = create_agent_from_message(db, session_id, create_hint, user_message)
        yield f"data: {json.dumps({'ephemeral_agent': {'action': 'created', 'agent': agent_to_dict(new_agent)}})}\n\n"

    active_agent = get_active_agent(db, session_id)
    agent_meta = f" · Agent: {active_agent.name}" if active_agent else ""

    history_before = get_messages(db, session_id)
    is_clarification_reply = (
        len(history_before) >= 2
        and history_before[-2].role == "assistant"
        and is_clarification_content(history_before[-2].content)
    )

    clarify_enabled = bot_settings.clarify_questions if bot_settings else True
    if not deep_research and clarify_enabled and not is_clarification_reply:
        recent = [(m.role, m.content) for m in history_before[:-1]]
        try:
            yield _activity_event("thinking", "Understanding", "Reading your request in detail")
            clarification = await check_clarification_needed(user_message, recent, bot_settings)
        except Exception:
            clarification = None
        if clarification:
            content = encode_clarification_message(clarification)
            assistant_msg = Message(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="assistant",
                content=content,
                created_at=datetime.utcnow(),
            )
            db.add(assistant_msg)
            session.updated_at = datetime.utcnow()
            db.commit()
            _mirror_message_to_cache(assistant_msg)
            yield clarification_event(clarification)
            yield f"data: {json.dumps({'done': True, 'clarification': True})}\n\n"
            return

    app_knowledge = format_app_knowledge_system_message(user_message)
    cross_hits = search_sessions(db, user_message, exclude_session_id=session_id)
    explicit_cross = detect_cross_session_intent(user_message)

    if explicit_cross and cross_hits:
        direct = format_which_chat_direct_answer(cross_hits)
        model_display_name = resolve_model_display(deep_research=False)
        yield f"data: {json.dumps({'model_display': model_display_name})}\n\n"
        if direct:
            async for event in stream_text(direct):
                yield event
            assistant_msg = Message(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="assistant",
                content=encode_model_message(direct, model_display_name),
                created_at=datetime.utcnow(),
            )
            db.add(assistant_msg)
            session.updated_at = datetime.utcnow()
            db.commit()
            _mirror_message_to_cache(assistant_msg)
            memory_service.store_exchange(session_id, user_message, direct)
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

    cross_session_context = (
        format_session_reference_system_message(cross_hits, explicit_lookup=explicit_cross)
        if cross_hits
        else None
    )
    ref_prefix = (
        format_user_visible_reference(cross_hits)
        if cross_hits and is_high_confidence(cross_hits, user_message) and not explicit_cross
        else ""
    )

    doc_hits = _retrieve_doc_hits(db, session_id, user_message)
    doc_citations = document_service.hits_to_citations(doc_hits) if doc_hits else []

    if not deep_research and is_complex_query(user_message):
        yield _activity_event("thinking", "Understanding", "Analyzing your request before answering")

    youtube_videos: list = []
    if not deep_research and detect_video_intent(user_message):
        yield _activity_event("searching", "Finding videos", "Searching YouTube for relevant content")
        try:
            youtube_videos = search_youtube(user_message, max_results=5)
        except Exception:
            youtube_videos = []
        if youtube_videos:
            yield youtube_event(youtube_videos)

    lc_messages = _build_langchain_messages(
        db,
        session_id,
        user_message,
        bot_settings,
        doc_hits=doc_hits,
        app_knowledge=app_knowledge,
        cross_session_context=cross_session_context,
    )
    build_mode = is_build_request(user_message)

    if youtube_videos and lc_messages and isinstance(lc_messages[0], SystemMessage):
        video_lines = ["## Recommended YouTube videos (already shown to the user)"]
        for i, v in enumerate(youtube_videos, 1):
            video_lines.append(
                f"{i}. **{v.get('title', 'Video')}** — {v.get('channel', 'YouTube')}\n"
                f"   {v.get('url', '')}\n"
                f"   {v.get('description', '')}"
            )
        lc_messages[0] = SystemMessage(
            content=lc_messages[0].content + "\n\n" + "\n".join(video_lines)
        )

    if doc_citations:
        yield f"data: {json.dumps({'doc_citations': doc_citations})}\n\n"

    if build_mode:
        yield f"data: {json.dumps({'build_mode': True})}\n\n"
        yield _activity_event(
            "planning",
            "Production build",
            "Scaffolding production-ready project structure",
        )

    web_sources: list = []
    if not deep_research and should_prefetch_web(bot_settings, user_message):
        from app.services.web_search_service import get_active_provider
        provider = get_active_provider()
        yield _activity_event("searching", "Searching the web", f"Looking up live results via {provider}")
        try:
            web_context, provider, count, sources = search_and_format(user_message)
            if count > 0:
                merge_sources(web_sources, sources)
            if count > 0 and lc_messages and isinstance(lc_messages[0], SystemMessage):
                lc_messages[0] = SystemMessage(content=lc_messages[0].content + "\n\n" + web_context)
        except Exception:
            pass
        yield _activity_event("analyzing", "Analyzing sources", "Reviewing search results")
        if web_sources:
            yield f"data: {json.dumps({'sources': web_sources})}\n\n"

    tools = build_integration_tools(
        db, bot_settings, user_message, web_sources, user_id=session.user_id
    )
    agent_model = active_agent.model_preference if active_agent and active_agent.model_preference else None

    active_repo_ids = bot_settings.active_github_repo_ids if bot_settings else []
    repo_meta = ""
    if active_repo_ids:
        _, is_relevant, repo_names = github_repo_service.get_relevant_context(
            db, active_repo_ids, user_message
        )
        if is_relevant and repo_names:
            repo_meta = f" · Repo ref: {', '.join(repo_names)}"
    build_meta = f" · {BUILD_MODE_META}" if build_mode else ""

    model_selection = bot_settings.model_selection if bot_settings else "mistral-large"
    model_display_name = resolve_model_display(
        model_id=model_selection,
        orchestrated=False,
        deep_research=deep_research,
    )
    yield f"data: {json.dumps({'model_display': model_display_name})}\n\n"

    full_response = ref_prefix
    if ref_prefix:
        async for event in stream_text(ref_prefix):
            yield event

    deep_research_sources: list = []
    try:
        if deep_research:
            async for event in stream_deep_research(user_message, bot_settings):
                if event.startswith("data: "):
                    try:
                        payload = json.loads(event[6:].strip())
                        if payload.get("done"):
                            continue
                        if payload.get("token"):
                            full_response += payload["token"]
                        research_meta = payload.get("research_meta")
                        if research_meta and research_meta.get("source_list"):
                            deep_research_sources = research_meta["source_list"]
                    except json.JSONDecodeError:
                        pass
                yield event
        elif tools:
            yield _activity_event("reasoning", "Reasoning", "Planning how to help")
            yield _activity_event("tools", "Using tools", "Running integrations")
            models = await fetch_mistral_models()
            plan = build_routing_plan(user_message, models, model_selection)
            if plan.mode == "multi":
                model_display_name = resolve_model_display(orchestrated=True)
                yield f"data: {json.dumps({'model_display': model_display_name})}\n\n"
            meta = plan.explanation
            if should_prefetch_web(bot_settings, user_message):
                from app.services.web_search_service import get_active_provider
                meta += f" · Web: {get_active_provider()}"
            if repo_meta:
                meta += repo_meta
            if build_meta:
                meta += build_meta
            if agent_meta:
                meta += agent_meta
            yield f"data: {json.dumps({'meta': meta})}\n\n"
            full_response, _ = await run_with_tools(
                db,
                lc_messages,
                bot_settings,
                model_id=agent_model or plan.primary_model,
                user_message=user_message,
                sources_collector=web_sources,
                user_id=session.user_id,
            )
            yield _activity_event("writing", "Writing", "Composing response")
            async for event in stream_text(full_response):
                yield event
        else:
            yield _activity_event("reasoning", "Reasoning", "Selecting the best approach")
            effective_settings = bot_settings
            effective_model_selection = model_selection
            if agent_model:
                effective_settings = (bot_settings or BotSettings()).model_copy(
                    update={"model_selection": agent_model}
                )
                effective_model_selection = agent_model
            if should_prefetch_web(bot_settings, user_message):
                from app.services.web_search_service import get_active_provider
                meta = f'Web search: {get_active_provider()}'
                if repo_meta:
                    meta += repo_meta
                if build_meta:
                    meta += build_meta
                if agent_meta:
                    meta += agent_meta
                yield f"data: {json.dumps({'meta': meta})}\n\n"
            elif build_mode:
                meta = BUILD_MODE_META
                if repo_meta:
                    meta += repo_meta
                if agent_meta:
                    meta += agent_meta
                yield f"data: {json.dumps({'meta': meta})}\n\n"
            elif agent_meta:
                yield f"data: {json.dumps({'meta': agent_meta.strip(' · ')})}\n\n"
            elif repo_meta:
                yield f"data: {json.dumps({'meta': repo_meta.strip(' · ')})}\n\n"
            models = await fetch_mistral_models()
            orch_plan = build_routing_plan(user_message, models, effective_model_selection)
            if orch_plan.mode == "multi":
                model_display_name = resolve_model_display(orchestrated=True)
                yield f"data: {json.dumps({'model_display': model_display_name})}\n\n"
            async for event in stream_orchestrated(
                lc_messages, user_message, effective_settings, effective_model_selection
            ):
                if event.startswith("data: "):
                    try:
                        payload = json.loads(event[6:].strip())
                        if payload.get("token"):
                            full_response += payload["token"]
                    except json.JSONDecodeError:
                        pass
                yield event
    except Exception as e:
        logger.exception("Chat stream failed session=%s: %s", session_id, e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
        return

    stored_sources = web_sources or deep_research_sources
    has_response = bool(full_response.strip())
    if has_response:
        stored_content = encode_sources_message(full_response, stored_sources) if stored_sources else full_response
        if youtube_videos:
            stored_content = encode_youtube_message(stored_content, youtube_videos)
        stored_content = encode_model_message(stored_content, model_display_name)
        assistant_msg = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content=stored_content,
            sources=json.dumps(doc_citations, ensure_ascii=False) if doc_citations else "",
            created_at=datetime.utcnow(),
        )
        db.add(assistant_msg)
        memory_service.store_exchange(session_id, user_message, full_response)
    else:
        yield f"data: {json.dumps({'error': 'No response was generated. Please try again.'})}\n\n"

    session.updated_at = datetime.utcnow()
    db.commit()
    if has_response:
        _mirror_message_to_cache(assistant_msg)

    try:
        from app.services.workspace_service import add_usage, log_audit, sync_session_artifacts
        if has_response:
            add_usage(db, session_id, user_message, full_response)
            sync_session_artifacts(db, session_id)
        log_audit(db, "chat", "stream_complete", f"session={session_id}", session_id)
    except Exception:
        logger.debug("workspace post-stream hooks failed", exc_info=True)

    if stored_sources:
        yield f"data: {json.dumps({'sources': stored_sources})}\n\n"
    if youtube_videos:
        yield youtube_event(youtube_videos)
    done_payload: dict = {"done": True, "model_display": model_display_name}
    if doc_citations:
        done_payload["doc_citations"] = doc_citations
    try:
        session = get_session(db, session_id)
        if session:
            done_payload["usage"] = {
                "prompt_tokens": int(session.prompt_tokens or 0),
                "completion_tokens": int(session.completion_tokens or 0),
                "total_tokens": int(session.prompt_tokens or 0) + int(session.completion_tokens or 0),
            }
    except Exception:
        pass
    yield f"data: {json.dumps(done_payload)}\n\n"
