"""Console chat sessions — one UUID per upload/workflow, messages in JSONB."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConsoleChatSession(Base):
    __tablename__ = "console_chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    messages: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    batch_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
