# routers/chat.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List

from app.core.chat_assistant import ChatTurn, get_chat_reply

router = APIRouter(prefix="", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: List[ChatTurn] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    try:
        reply = get_chat_reply(payload.message, payload.history)
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="Chat assistant is not configured.",
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Chat assistant is temporarily unavailable.",
        )

    return ChatResponse(reply=reply)
