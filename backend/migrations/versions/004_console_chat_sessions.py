"""Console chat sessions (UUID per upload workflow).

Revision ID: 004_console_chat_sessions
Revises: 004_dataset_id_counters
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "004_console_chat_sessions"
down_revision: Union[str, None] = "004_dataset_id_counters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS console_chat_sessions (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_email   TEXT NOT NULL,
                messages     JSONB NOT NULL DEFAULT '[]'::jsonb,
                batch_id     TEXT,
                pdf_job_id   TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                updated_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_console_chat_sessions_user
                ON console_chat_sessions (user_email)
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS console_chat_sessions"))
