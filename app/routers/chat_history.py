from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    ChatConversation,
    ChatConversationListResponse,
    ChatConversationResponse,
    ChatConversationSaveRequest,
    ChatConversationSummaryResponse,
    ChatHistoryMessageResponse,
    ChatMessage,
    SystemUser,
)
from app.time_utils import utc_now

router = APIRouter(prefix="/chat/conversations", tags=["chat-history"])


def _default_title(body: ChatConversationSaveRequest) -> str:
    title = (body.title or "").strip()
    if title:
        return title[:200]
    for message in body.messages:
        if message.role == "user" and message.content.strip():
            return message.content.strip()[:200]
    return "新对话"


def _message_response(message: ChatMessage) -> ChatHistoryMessageResponse:
    return ChatHistoryMessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        thinking=message.thinking,
        sources=message.sources,
        web_search=message.web_search,
        sequence=message.sequence,
        created_at=message.created_at,
    )


async def _message_count(db: AsyncSession, conversation_id: int) -> int:
    result = await db.execute(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.conversation_id == conversation_id
        )
    )
    return int(result.scalar() or 0)


async def _summary_response(
    db: AsyncSession, conversation: ChatConversation
) -> ChatConversationSummaryResponse:
    return ChatConversationSummaryResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        workspace_id=conversation.workspace_id,
        knowledge_base_id=conversation.knowledge_base_id,
        title=conversation.title,
        scope=conversation.scope,
        web_search=bool(conversation.web_search),
        web_search_provider=conversation.web_search_provider,
        message_count=await _message_count(db, conversation.id),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


async def _full_response(
    db: AsyncSession, conversation: ChatConversation
) -> ChatConversationResponse:
    summary = await _summary_response(db, conversation)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.sequence.asc(), ChatMessage.id.asc())
    )
    return ChatConversationResponse(
        **summary.model_dump(),
        messages=[_message_response(message) for message in result.scalars().all()],
    )


async def _get_user_conversation(
    db: AsyncSession, user: SystemUser, conversation_id: int
) -> ChatConversation:
    result = await db.execute(
        select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


async def _replace_messages(
    db: AsyncSession,
    conversation: ChatConversation,
    body: ChatConversationSaveRequest,
) -> None:
    await db.execute(
        delete(ChatMessage).where(ChatMessage.conversation_id == conversation.id)
    )
    for index, message in enumerate(body.messages):
        db.add(
            ChatMessage(
                conversation_id=conversation.id,
                user_id=conversation.user_id,
                role=message.role,
                content=message.content,
                thinking=message.thinking,
                sources=message.sources,
                web_search=message.web_search,
                sequence=index,
            )
        )


@router.get("", response_model=ChatConversationListResponse)
@router.get("/", response_model=ChatConversationListResponse)
async def list_conversations(
    knowledge_base_id: int | None = Query(default=None),
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationListResponse:
    query = select(ChatConversation).where(ChatConversation.user_id == current_user.id)
    if knowledge_base_id is not None:
        query = query.where(ChatConversation.knowledge_base_id == knowledge_base_id)
    query = query.order_by(
        ChatConversation.updated_at.desc(), ChatConversation.id.desc()
    )
    result = await db.execute(query)
    items = [
        await _summary_response(db, conversation)
        for conversation in result.scalars().all()
    ]
    return ChatConversationListResponse(items=items)


@router.post("", response_model=ChatConversationResponse)
@router.post("/", response_model=ChatConversationResponse)
async def create_conversation(
    body: ChatConversationSaveRequest,
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationResponse:
    conversation = ChatConversation(
        user_id=current_user.id,
        workspace_id=body.workspace_id,
        knowledge_base_id=body.knowledge_base_id,
        title=_default_title(body),
        scope=body.scope,
        web_search=body.web_search,
        web_search_provider=body.web_search_provider,
    )
    db.add(conversation)
    await db.flush()
    await _replace_messages(db, conversation, body)
    await db.commit()
    await db.refresh(conversation)
    return await _full_response(db, conversation)


@router.get("/{conversation_id}", response_model=ChatConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationResponse:
    conversation = await _get_user_conversation(db, current_user, conversation_id)
    return await _full_response(db, conversation)


@router.put("/{conversation_id}", response_model=ChatConversationResponse)
async def update_conversation(
    conversation_id: int,
    body: ChatConversationSaveRequest,
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationResponse:
    conversation = await _get_user_conversation(db, current_user, conversation_id)
    conversation.title = _default_title(body)
    conversation.workspace_id = body.workspace_id
    conversation.knowledge_base_id = body.knowledge_base_id
    conversation.scope = body.scope
    conversation.web_search = body.web_search
    conversation.web_search_provider = body.web_search_provider
    conversation.updated_at = utc_now()
    await _replace_messages(db, conversation, body)
    await db.commit()
    await db.refresh(conversation)
    return await _full_response(db, conversation)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: int,
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    conversation = await _get_user_conversation(db, current_user, conversation_id)
    await db.execute(
        delete(ChatMessage).where(ChatMessage.conversation_id == conversation.id)
    )
    await db.delete(conversation)
    await db.commit()
    return Response(status_code=204)
