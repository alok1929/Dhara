"""Console chat session CRUD."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.db.models.console_chat import ConsoleChatSession


def create_session(
    session: Session,
    *,
    user_email: str,
    batch_id: str | None = None,
    pdf_job_id: str | None = None,
) -> ConsoleChatSession:
    row = ConsoleChatSession(
        id=uuid.uuid4(),
        user_email=user_email,
        messages=[],
        batch_id=batch_id,
        pdf_job_id=pdf_job_id,
    )
    session.add(row)
    session.flush()
    return row


def get_session(
    session: Session,
    session_id: uuid.UUID,
    user_email: str,
) -> ConsoleChatSession | None:
    row = session.scalar(
        select(ConsoleChatSession).where(
            ConsoleChatSession.id == session_id,
            ConsoleChatSession.user_email == user_email,
        )
    )
    return row


def save_messages(
    session: Session,
    row: ConsoleChatSession,
    messages: list[Any],
) -> ConsoleChatSession:
    row.messages = messages
    session.flush()
    return row


def update_links(
    session: Session,
    row: ConsoleChatSession,
    *,
    batch_id: str | None = None,
    pdf_job_id: str | None = None,
) -> ConsoleChatSession:
    if batch_id is not None:
        row.batch_id = batch_id
    if pdf_job_id is not None:
        row.pdf_job_id = pdf_job_id
    session.execute(
        update(ConsoleChatSession)
        .where(ConsoleChatSession.id == row.id)
        .values(
            batch_id=row.batch_id,
            pdf_job_id=row.pdf_job_id,
            updated_at=func.now(),
        )
    )
    session.flush()
    return row
