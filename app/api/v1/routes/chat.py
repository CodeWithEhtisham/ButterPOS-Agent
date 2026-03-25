"""POST /chat/message — main chatbot endpoint."""

from fastapi import APIRouter, Depends

from app.schemas.chat import ChatMessageRequest, ChatMessageResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(request: ChatMessageRequest):
    raise NotImplementedError("Chat endpoint not yet implemented")
