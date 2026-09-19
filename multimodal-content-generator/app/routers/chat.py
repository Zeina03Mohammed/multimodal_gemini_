"""
Unified chat endpoints.

One conversational thread where Gemini decides, per message, whether to
just reply, search the user's uploaded documents, or generate an image -
see app/services/chat_engine.py for how that routing works. This is what
the Flutter app's chat screen talks to.
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    ChatMessage,
    ChatSendRequest,
    ChatSendResponse,
    ConversationDetail,
    ConversationSummary,
)
from app.services import chat_engine, chat_store

router = APIRouter(prefix="/chat", tags=["chat"])

_TITLE_MAX_LENGTH = 40


@router.post("/conversations", response_model=ConversationSummary)
def create_conversation() -> ConversationSummary:
    created = chat_store.create_conversation(title="New chat")
    return ConversationSummary(**created)


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations() -> list[ConversationSummary]:
    return [ConversationSummary(**c) for c in chat_store.list_conversations()]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str) -> ConversationDetail:
    if not chat_store.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conversations = {c["conversation_id"]: c for c in chat_store.list_conversations()}
    conversation = conversations[conversation_id]
    messages = chat_store.get_messages(conversation_id)

    return ConversationDetail(
        **conversation,
        messages=[ChatMessage(**m) for m in messages],
    )


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict:
    if not chat_store.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"deleted": conversation_id}


@router.post("/conversations/{conversation_id}/messages", response_model=ChatSendResponse)
def send_message(conversation_id: str, request: ChatSendRequest) -> ChatSendResponse:
    if not chat_store.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")

    history = chat_store.get_messages(conversation_id)
    chat_store.add_message(conversation_id, role="user", text=request.message)

    if not history:
        title = request.message[:_TITLE_MAX_LENGTH]
        if len(request.message) > _TITLE_MAX_LENGTH:
            title += "..."
        chat_store.update_title(conversation_id, title)

    try:
        reply = chat_engine.send_message(history, request.message)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    saved = chat_store.add_message(
        conversation_id,
        role="model",
        text=reply["text"],
        image_base64=reply["image_base64"],
        image_mime_type=reply["image_mime_type"],
        sources=reply["sources"],
    )

    return ChatSendResponse(conversation_id=conversation_id, message=ChatMessage(**saved))
