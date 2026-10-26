"""Per-user LLM API key storage (encrypted at rest)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.core.crypto import (
    CredentialCryptoError,
    decrypt_secret,
    encrypt_secret,
    is_fernet_token,
)
from app.db.models.catalogue import LlmApiKey
from app.services.llm.routing import CHAT_SOURCE_CLOUD, LlmChatRouting

_NO_CLOUD_KEY_PLACEHOLDER = "__dhara_no_cloud_key__"


def _is_real_key(plaintext: str | None) -> bool:
    text = (plaintext or "").strip()
    return bool(text) and text != _NO_CLOUD_KEY_PLACEHOLDER


@dataclass(frozen=True)
class LlmKeyStatus:
    configured: bool
    provider: str | None
    updated_at: str | None
    api_key: str | None = None
    crypto_error: bool = False
    chat_source: str = "cloud"
    on_prem_model: str | None = None


def get(session: Session, user_email: str) -> LlmApiKey | None:
    return session.scalar(select(LlmApiKey).where(LlmApiKey.user_email == user_email))


def _routing_from_row(row: LlmApiKey | None) -> LlmChatRouting:
    if row is None:
        return LlmChatRouting()
    source = (getattr(row, "chat_source", None) or CHAT_SOURCE_CLOUD).strip().lower()
    model = (getattr(row, "on_prem_model", None) or "").strip() or None
    return LlmChatRouting(chat_source=source, on_prem_model=model).normalized()


def get_routing(session: Session, user_email: str) -> LlmChatRouting:
    return _routing_from_row(get(session, user_email))


def upsert_routing(
    session: Session,
    user_email: str,
    *,
    chat_source: str,
    on_prem_model: str | None = None,
) -> LlmApiKey:
    routing = LlmChatRouting(
        chat_source=chat_source, on_prem_model=on_prem_model
    ).normalized()
    row = get(session, user_email)
    if row is None:
        row = LlmApiKey(
            user_email=user_email,
            api_key=encrypt_secret(_NO_CLOUD_KEY_PLACEHOLDER),
            provider=None,
            chat_source=routing.chat_source,
            on_prem_model=routing.on_prem_model,
        )
        session.add(row)
    else:
        row.chat_source = routing.chat_source
        row.on_prem_model = routing.on_prem_model
        row.updated_at = func.now()
    session.flush()
    return row


def get_status(session: Session, user_email: str) -> LlmKeyStatus:
    """Status for the key owner: ``configured`` only when decrypt succeeds."""
    row = get(session, user_email)
    routing = _routing_from_row(row)
    if not row or not (row.api_key or "").strip():
        return LlmKeyStatus(
            configured=False,
            provider=None,
            updated_at=None,
            chat_source=routing.chat_source,
            on_prem_model=routing.on_prem_model,
        )
    updated_at = row.updated_at.isoformat() if row.updated_at else None
    provider = (row.provider or "").strip().lower() or None
    raw = (row.api_key or "").strip()
    plaintext: str | None = None
    if is_fernet_token(raw):
        try:
            plaintext = decrypt_secret(raw)
        except CredentialCryptoError:
            return LlmKeyStatus(
                configured=False,
                provider=provider,
                updated_at=updated_at,
                crypto_error=True,
                chat_source=routing.chat_source,
                on_prem_model=routing.on_prem_model,
            )
    else:
        plaintext = raw
    if not _is_real_key(plaintext):
        return LlmKeyStatus(
            configured=False,
            provider=provider,
            updated_at=updated_at,
            chat_source=routing.chat_source,
            on_prem_model=routing.on_prem_model,
        )
    return LlmKeyStatus(
        configured=True,
        provider=provider,
        updated_at=updated_at,
        api_key=plaintext,
        chat_source=routing.chat_source,
        on_prem_model=routing.on_prem_model,
    )


def get_decrypted(
    session: Session, user_email: str
) -> tuple[str | None, str | None]:
    """Return ``(api_key, provider)`` for server-side provider calls only."""
    status = get_status(session, user_email)
    if not status.configured or not status.api_key:
        return None, None
    return status.api_key, status.provider


def upsert(
    session: Session, user_email: str, api_key: str, provider: str | None = None
) -> LlmApiKey:
    ciphertext = encrypt_secret(api_key.strip())
    row = get(session, user_email)
    if row:
        row.api_key = ciphertext
        row.provider = provider
        row.updated_at = func.now()
        session.flush()
        return row
    row = LlmApiKey(
        user_email=user_email,
        api_key=ciphertext,
        provider=provider,
        chat_source=CHAT_SOURCE_CLOUD,
    )
    session.add(row)
    session.flush()
    return row


def delete_key(session: Session, user_email: str) -> bool:
    result = session.execute(
        delete(LlmApiKey).where(LlmApiKey.user_email == user_email)
    )
    session.flush()
    return (result.rowcount or 0) > 0
