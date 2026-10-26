"""Per-user LLM chat routing (cloud vs on-prem).

Revision ID: 005_llm_chat_routing
Revises: 004_console_chat_sessions
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "005_llm_chat_routing"
down_revision: Union[str, None] = "004_console_chat_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            ALTER TABLE llm_api_keys
              ADD COLUMN IF NOT EXISTS chat_source TEXT NOT NULL DEFAULT 'cloud';
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE llm_api_keys
              ADD COLUMN IF NOT EXISTS on_prem_model TEXT;
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE llm_api_keys DROP COLUMN IF EXISTS on_prem_model;"))
    conn.execute(text("ALTER TABLE llm_api_keys DROP COLUMN IF EXISTS chat_source;"))
