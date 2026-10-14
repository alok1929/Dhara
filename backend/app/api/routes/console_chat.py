"""Console chat sessions — UUID per upload, persisted message history."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_user_email
from app.db.repositories import console_chat as chat_repo

router = APIRouter()


class CreateChatSessionBody(BaseModel):
    batch_id: str | None = None
    pdf_job_id: str | None = None


class SaveChatMessagesBody(BaseModel):
    messages: list[Any] = Field(default_factory=list)


class LinkChatSessionBody(BaseModel):
    batch_id: str | None = None
    pdf_job_id: str | None = None


def _session_payload(row) -> dict:
    return {
        "session_id": str(row.id),
        "messages": row.messages or [],
        "batch_id": row.batch_id,
        "pdf_job_id": row.pdf_job_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post("/api/console/chat/sessions")
async def create_chat_session(
    body: CreateChatSessionBody,
    user_email: str = Depends(require_user_email),
    db: Session = Depends(get_db),
):
    row = chat_repo.create_session(
        db,
        user_email=user_email,
        batch_id=(body.batch_id or "").strip() or None,
        pdf_job_id=(body.pdf_job_id or "").strip() or None,
    )
    db.commit()
    return _session_payload(row)


@router.get("/api/console/chat/sessions/{session_id}")
async def get_chat_session(
    session_id: str,
    user_email: str = Depends(require_user_email),
    db: Session = Depends(get_db),
):
    try:
        sid = uuid.UUID(session_id)
    except ValueError as e:
        raise HTTPException(400, "Invalid session_id") from e
    row = chat_repo.get_session(db, sid, user_email)
    if not row:
        raise HTTPException(404, "Chat session not found")
    return _session_payload(row)


@router.put("/api/console/chat/sessions/{session_id}/messages")
async def save_chat_messages(
    session_id: str,
    body: SaveChatMessagesBody,
    user_email: str = Depends(require_user_email),
    db: Session = Depends(get_db),
):
    try:
        sid = uuid.UUID(session_id)
    except ValueError as e:
        raise HTTPException(400, "Invalid session_id") from e
    row = chat_repo.get_session(db, sid, user_email)
    if not row:
        raise HTTPException(404, "Chat session not found")
    if not isinstance(body.messages, list):
        raise HTTPException(400, "messages must be an array")
    chat_repo.save_messages(db, row, body.messages)
    db.commit()
    return _session_payload(row)


@router.patch("/api/console/chat/sessions/{session_id}")
async def link_chat_session(
    session_id: str,
    body: LinkChatSessionBody,
    user_email: str = Depends(require_user_email),
    db: Session = Depends(get_db),
):
    try:
        sid = uuid.UUID(session_id)
    except ValueError as e:
        raise HTTPException(400, "Invalid session_id") from e
    row = chat_repo.get_session(db, sid, user_email)
    if not row:
        raise HTTPException(404, "Chat session not found")
    chat_repo.update_links(
        db,
        row,
        batch_id=body.batch_id,
        pdf_job_id=body.pdf_job_id,
    )
    db.commit()
    return _session_payload(row)
