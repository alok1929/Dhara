"""On-prem model catalogue for Settings (read-only)."""
from fastapi import APIRouter, Depends

from app.api.dependencies import CurrentUser, require_user
from app.db.repositories import llm_keys as llm_repo
from app.db.session import get_db
from app.services.llm.model_catalog import build_llm_catalog_payload
from sqlalchemy.orm import Session

router = APIRouter(tags=["Settings"])


@router.get("/api/llm-catalog", summary="On-prem LLM catalogue and gateway status")
async def get_llm_catalog(
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    routing = llm_repo.get_routing(db, user.email)
    return build_llm_catalog_payload(
        user_chat_source=routing.chat_source,
        user_on_prem_model=routing.on_prem_model,
    )
