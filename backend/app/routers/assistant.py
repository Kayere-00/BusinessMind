"""Assistant APIs: legacy grounded answers plus persistent conversational chat."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..database import SessionLocal, get_db
from ..deps import analyst_or_admin, get_current_user
from ..models import AssistantConversation, AssistantMessage, BusinessContext, Dataset, Role, User
from ..schemas import (
    AskRequest,
    AskResponse,
    AssistantMessageCreate,
    AssistantMessageOut,
    BusinessContextOut,
    BusinessContextUpdate,
    ConversationCreateRequest,
    ConversationDetail,
    ConversationOut,
)
from ..services import assistant_agent, assistant_tools, llm, nlq, profiling, storage
from .datasets import _get_org_dataset

logger = logging.getLogger("businessmind.assistant")
router = APIRouter(prefix="/api/assistant", tags=["assistant"])
settings = get_settings()


def _conversation(
    db: Session,
    conversation_id: str,
    current: User,
    *,
    with_messages: bool = False,
) -> AssistantConversation:
    query = select(AssistantConversation).where(
        AssistantConversation.id == conversation_id,
        AssistantConversation.org_id == current.org_id,
        AssistantConversation.user_id == current.id,
    )
    if with_messages:
        query = query.options(selectinload(AssistantConversation.messages))
    conversation = db.scalar(query)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    return conversation


def _message_out(message: AssistantMessage) -> AssistantMessageOut:
    return AssistantMessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        metadata=message.message_metadata or {},
        created_at=message.created_at,
    )


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Keep the original deterministic API for existing clients."""
    ds = _get_org_dataset(db, payload.dataset_id, current.org_id)
    path = storage.resolve_within(ds.stored_path, current.org_id)
    df = profiling.load_dataframe(str(path))
    df, _ = profiling.profile_dataframe(df)

    result = nlq.answer_question(df, payload.question)

    narrative, source = None, "none"
    if result.get("computed"):
        narrative = await llm.narrate(result["computed"], question=payload.question)
        if narrative:
            source = "ollama"
    return AskResponse(
        answer=result["answer"],
        narrative=narrative,
        narrative_source=source,  # type: ignore[arg-type]
        chart=result.get("chart"),
        table=result.get("table"),
        computed=result.get("computed"),
    )


@router.get("/status")
async def assistant_status(current: User = Depends(get_current_user)):
    return await llm.health()


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(AssistantConversation)
        .where(
            AssistantConversation.org_id == current.org_id,
            AssistantConversation.user_id == current.id,
        )
        .order_by(AssistantConversation.updated_at.desc())
    ).all()


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreateRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dataset: Dataset | None = None
    if payload.dataset_id:
        dataset = _get_org_dataset(db, payload.dataset_id, current.org_id)
    title = (payload.title or (dataset.name if dataset else "New conversation")).strip()
    conversation = AssistantConversation(
        org_id=current.org_id,
        user_id=current.id,
        dataset_id=dataset.id if dataset else None,
        title=title[:120],
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _conversation(db, conversation_id, current, with_messages=True)
    return ConversationDetail(
        id=conversation.id,
        dataset_id=conversation.dataset_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        summary=conversation.summary,
        messages=[_message_out(message) for message in conversation.messages],
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _conversation(db, conversation_id, current)
    db.delete(conversation)
    db.commit()


def _event(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


@router.post("/conversations/{conversation_id}/messages")
async def create_message(
    conversation_id: str,
    payload: AssistantMessageCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _conversation(db, conversation_id, current)
    question = payload.content.strip()
    if not question:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Message cannot be blank.")

    dataset: Dataset | None = None
    dataframe = None
    if conversation.dataset_id:
        dataset = _get_org_dataset(db, conversation.dataset_id, current.org_id)
        dataset_path = storage.resolve_within(dataset.stored_path, current.org_id)
        dataframe = profiling.load_dataframe(str(dataset_path))
        dataframe, _ = profiling.profile_dataframe(dataframe)

    message_query = (
        select(AssistantMessage)
        .where(
            AssistantMessage.conversation_id == conversation.id,
            AssistantMessage.org_id == current.org_id,
        )
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
    )
    history_count = db.scalar(
        select(func.count(AssistantMessage.id)).where(
            AssistantMessage.conversation_id == conversation.id,
            AssistantMessage.org_id == current.org_id,
        )
    ) or 0
    if conversation.title == "New conversation":
        conversation.title = question[:117] + ("..." if len(question) > 120 else "")
    user_message = AssistantMessage(
        org_id=current.org_id,
        conversation_id=conversation.id,
        role="user",
        content=question,
    )
    db.add(user_message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()

    business_context = db.get(BusinessContext, current.org_id)
    context_text = business_context.context_text if business_context else None
    can_create_report = current.role in {Role.admin, Role.analyst}
    conversation_id_value = conversation.id
    org_id_value = current.org_id
    dataset_id_value = dataset.id if dataset else None
    summary = conversation.summary
    history_limit = max(4, min(settings.OLLAMA_HISTORY_MESSAGES, 40))
    summarized_count = min(conversation.summarized_message_count, history_count)
    summary_tail_count = max(8, history_limit // 2)
    older_message_count = max(0, history_count - summarized_count - summary_tail_count)
    older_rows = db.scalars(
        message_query.offset(summarized_count).limit(min(older_message_count, history_limit))
    ).all()
    summary_messages = [{"role": row.role, "content": row.content} for row in older_rows]
    summary_target = summarized_count + len(summary_messages)
    recent_offset = max(0, history_count - history_limit)
    recent_rows = db.scalars(message_query.offset(recent_offset).limit(history_limit)).all()
    history = [{"role": row.role, "content": row.content} for row in recent_rows]

    async def stream():
        nonlocal summary, summarized_count
        yield _event("status", {"text": "Thinking"})
        if summary_messages:
            try:
                summary = await llm.summarize_conversation(summary_messages, summary)
                summarized_count = summary_target
                with SessionLocal() as stream_db:
                    stored_conversation = stream_db.get(
                        AssistantConversation, conversation_id_value
                    )
                    if stored_conversation is None:
                        yield _event("error", {"message": "Conversation no longer exists."})
                        return
                    stored_conversation.summary = summary
                    stored_conversation.summarized_message_count = summarized_count
                    stream_db.commit()
            except llm.OllamaUnavailable as exc:
                logger.info("Conversation summary skipped id=%s reason=%s", conversation_id_value, exc)

        model_history = history[max(0, summarized_count - recent_offset):]
        answer = None
        metadata: dict[str, Any] = {}
        try:
            async for item in assistant_agent.respond(
                question,
                model_history,
                context_text,
                summary,
                dataframe,
                dataset_id_value,
                can_create_report=can_create_report,
            ):
                if item["type"] == "status":
                    yield _event("status", {"text": item["text"]})
                elif item["type"] == "delta":
                    yield _event("delta", {"text": item["text"]})
                elif item["type"] == "complete":
                    answer = item["content"]
                    metadata = item["metadata"]
        except Exception:
            logger.exception(
                "Assistant message generation failed org_id=%s user_id=%s conversation_id=%s",
                org_id_value,
                current.id,
                conversation_id_value,
            )
            yield _event("error", {"message": "The assistant could not complete this response. Retry your message."})
            return

        if answer is None:
            logger.error("Assistant generation ended without a final answer conversation_id=%s", conversation.id)
            yield _event("error", {"message": "The assistant did not return a response. Retry your message."})
            return

        assistant_message = AssistantMessage(
            org_id=org_id_value,
            conversation_id=conversation_id_value,
            role="assistant",
            content=answer,
            message_metadata=metadata,
        )
        try:
            with SessionLocal() as stream_db:
                stored_conversation = stream_db.get(
                    AssistantConversation, conversation_id_value
                )
                if stored_conversation is None:
                    yield _event("error", {"message": "Conversation no longer exists."})
                    return
                stream_db.add(assistant_message)
                stored_conversation.updated_at = datetime.now(timezone.utc)
                stream_db.commit()
                stream_db.refresh(assistant_message)
                response_message = _message_out(assistant_message).model_dump(mode="json")
        except Exception:
            logger.exception(
                "Could not persist assistant response org_id=%s conversation_id=%s",
                org_id_value,
                conversation_id_value,
            )
            yield _event("error", {"message": "The response could not be saved. Please retry."})
            return
        yield _event(
            "complete",
            {"message": response_message},
        )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/context", response_model=BusinessContextOut)
def get_business_context(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    context = db.get(BusinessContext, current.org_id)
    if context is None:
        return BusinessContextOut(context_text="", updated_at=None)
    return BusinessContextOut(context_text=context.context_text, updated_at=context.updated_at)


@router.put("/context", response_model=BusinessContextOut)
def update_business_context(
    payload: BusinessContextUpdate,
    current: User = Depends(analyst_or_admin),
    db: Session = Depends(get_db),
):
    text = payload.context_text.strip()
    context = db.get(BusinessContext, current.org_id)
    if not text:
        if context:
            db.delete(context)
            db.commit()
        return BusinessContextOut(context_text="", updated_at=None)
    if context is None:
        context = BusinessContext(org_id=current.org_id, context_text=text, updated_by=current.id)
        db.add(context)
    else:
        context.context_text = text
        context.updated_by = current.id
        context.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(context)
    return BusinessContextOut(context_text=context.context_text, updated_at=context.updated_at)


@router.delete("/context", status_code=status.HTTP_204_NO_CONTENT)
def delete_business_context(
    current: User = Depends(analyst_or_admin),
    db: Session = Depends(get_db),
):
    context = db.get(BusinessContext, current.org_id)
    if context:
        db.delete(context)
        db.commit()
