"""GET/POST the authenticated caller's stored LLM API key."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_user
from app.core.crypto import CredentialCryptoError
from app.core.permissions import MUTATING_ROLES, require_roles
from app.db.repositories import llm_keys as llm_repo
from app.db.session import get_db

router = APIRouter(tags=["Settings"])


def _status_payload(status: llm_repo.LlmKeyStatus, *, extra: dict | None = None) -> dict:
    body = {
        "configured": status.configured,
        "provider": status.provider,
        "updated_at": status.updated_at,
        "api_key": status.api_key if status.configured else None,
        "crypto_error": status.crypto_error,
        "chat_source": status.chat_source,
        "on_prem_model": status.on_prem_model,
    }
    if extra:
        body.update(extra)
    return body


@router.get("/api/llm-key", summary="Get LLM credential (decrypted for owner)")
async def get_llm_key(
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    status = llm_repo.get_status(db, user.email)
    return _status_payload(status)


@router.post("/api/llm-key", summary="Save or clear stored LLM API key")
async def save_llm_key(
    request: Request,
    user: CurrentUser = Depends(require_roles(*MUTATING_ROLES)),
    db: Session = Depends(get_db),
):
    data = await request.json()
    api_key = (data.get("api_key") or "").strip()
    provider = (data.get("provider") or "").strip() or None
    if provider:
        provider = provider.lower()
        if provider in ("meity-empanelled llm", "self-hosted"):
            provider = "openai" if provider.startswith("meity") else provider
    if not api_key:
        llm_repo.delete_key(db, user.email)
        return {
            "status": "cleared",
            "configured": False,
            "provider": None,
            "api_key": None,
            "crypto_error": False,
            "updated_at": None,
        }
    try:
        llm_repo.upsert(db, user.email, api_key, provider)
    except CredentialCryptoError as e:
        raise HTTPException(500, str(e)) from e
    status = llm_repo.get_status(db, user.email)
    return _status_payload(status, extra={"status": "saved"})


@router.post("/api/llm-chat-mode", summary="Choose cloud API key vs on-prem gateway")
async def save_llm_chat_mode(
    request: Request,
    user: CurrentUser = Depends(require_roles(*MUTATING_ROLES)),
    db: Session = Depends(get_db),
):
    data = await request.json()
    chat_source = (data.get("chat_source") or "").strip().lower()
    on_prem_model = (data.get("on_prem_model") or "").strip() or None
    if chat_source not in ("cloud", "on_prem"):
        raise HTTPException(400, "chat_source must be 'cloud' or 'on_prem'")
    try:
        llm_repo.upsert_routing(
            db,
            user.email,
            chat_source=chat_source,
            on_prem_model=on_prem_model,
        )
    except CredentialCryptoError as e:
        raise HTTPException(500, str(e)) from e
    status = llm_repo.get_status(db, user.email)
    return _status_payload(status, extra={"status": "saved"})
