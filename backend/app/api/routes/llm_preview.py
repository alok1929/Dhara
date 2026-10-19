"""llm_preview routes — chat interface on the same extraction job_id as guided Preview."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import (
    CurrentUser,
    get_db,
    require_user,
    resolve_llm_credentials,
)
from app.services.llm_preview import (
    build_llm_preview_catalog,
    execute_action_plan,
    plan_from_user_request,
)
from app.services.llm_preview.schemas import LlmInputResponse
from app.services.preview import (
    PreviewJobError,
    append_llm_turn,
    apply_overlay_to_job_reviews,
    ensure_preview_pipeline_step,
    get_llm_preview_catalog,
    get_llm_preview_meta,
    job_visible_to,
    overlay_client_tables,
    require_finished_job,
    review_tables_for_job,
    set_llm_preview_catalog,
    soft_delete_tables,
)
from app.workers.extraction_jobs import (
    _get_pdf_job,
    _pdf_jobs_lock,
    _save_pdf_job,
)

router = APIRouter(tags=["LLM Preview"])


def _require_api_key(request: Request, user: CurrentUser, db: Session) -> str:
    api_key, _provider = resolve_llm_credentials(request, user.email, db=db)
    if not (api_key or "").strip():
        raise HTTPException(400, "Save an LLM API key in Settings before using llm_preview")
    return api_key.strip()


@router.post("/api/llm_preview/jobs/{job_id}/llm_preview_data")
async def post_llm_preview_data(
    job_id: str,
    request: Request,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """
    Store a compact catalog for chat mode on this extraction job.

    Body:
    - ``tables`` (optional): compact stubs overlay (title / summary fields only)
    - ``force_summarize`` (optional bool): if true, run LangChain rewrite (needs API key)

    Default path maps stubs → ``{table_id, name, summary}`` with **no LLM**.
    Catalog is stored on ``job.reviews.__llm_preview``.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    force_summarize = bool(body.get("force_summarize"))
    api_key = None
    if force_summarize:
        api_key = _require_api_key(request, user, db)

    with _pdf_jobs_lock:
        job = _get_pdf_job(job_id)
        try:
            job = require_finished_job(job, user=user)
        except PreviewJobError as e:
            raise HTTPException(e.status_code, e.message) from e
        tables = review_tables_for_job(job)
        overlay_client_tables(tables, body.get("tables"))

    try:
        if force_summarize:
            catalog = await asyncio.to_thread(
                build_llm_preview_catalog,
                tables,
                force_summarize=True,
                api_key=api_key,
            )
        else:
            catalog = build_llm_preview_catalog(tables, force_summarize=False)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Could not build llm_preview catalog: {e}") from e

    with _pdf_jobs_lock:
        job = _get_pdf_job(job_id)
        if not job_visible_to(job, user):
            raise HTTPException(404, "Job not found")
        ensure_preview_pipeline_step(job)
        set_llm_preview_catalog(job, catalog, source_table_count=len(tables))
        _save_pdf_job(job)
        meta = get_llm_preview_meta(job)

    return {
        "job_id": job_id,
        "tables": catalog,
        "updated_at": meta.get("updated_at"),
        "source_table_count": meta.get("source_table_count"),
        "pipeline_step": meta.get("pipeline_step"),
        "last_turns": meta.get("last_turns") or [],
        "force_summarize": force_summarize,
    }


@router.get("/api/llm_preview/jobs/{job_id}/llm_preview_data")
async def get_llm_preview_data(
    job_id: str,
    user: CurrentUser = Depends(require_user),
):
    """Return stored table names + summaries for this job (same job_id as guided)."""
    with _pdf_jobs_lock:
        job = _get_pdf_job(job_id)
        try:
            job = require_finished_job(job, user=user)
        except PreviewJobError as e:
            raise HTTPException(e.status_code, e.message) from e
        meta = get_llm_preview_meta(job)
        catalog = meta.get("catalog")

    if catalog is None:
        raise HTTPException(
            404,
            "llm_preview catalog not built yet — POST llm_preview_data or send a user_request to llm_input",
        )

    return {
        "job_id": job_id,
        "tables": catalog,
        "updated_at": meta.get("updated_at"),
        "source_table_count": meta.get("source_table_count"),
        "pipeline_step": meta.get("pipeline_step"),
        "last_turns": meta.get("last_turns") or [],
    }


async def _handle_llm_input(
    job_id: str,
    request: Request,
    user: CurrentUser,
    db: Session,
):
    """
    Interpret ``user_request`` over the job catalog and return ``table_data``.

    Body:
    - user_request (required)
    - prompt (optional steward context)
    - tables (optional overlay — same shape as Preview / ai-search)
    - persist_reviews (optional bool) — write overlay into job.reviews for guided handoff
    - refresh (optional bool) — rebuild catalog from current tables (stubs, no LLM)
    - force_summarize (optional bool) — with refresh, rewrite catalog via LangChain
    - confirm_delete (optional bool) — for delete/bulk_delete, soft-delete via the same
      ``deleted_table_ids`` path as guided Preview (POST /pdf/.../tables/delete)
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    user_request = str(
        body.get("user_request") or body.get("user_query") or ""
    ).strip()
    if not user_request:
        raise HTTPException(400, "user_request (or user_query) is required")
    prompt = str(body.get("prompt") or "").strip() or None
    persist_reviews = bool(body.get("persist_reviews"))
    refresh = bool(body.get("refresh"))
    force_summarize = bool(body.get("force_summarize"))
    confirm_delete = bool(body.get("confirm_delete"))
    client_tables = body.get("tables")

    api_key = _require_api_key(request, user, db)

    with _pdf_jobs_lock:
        job = _get_pdf_job(job_id)
        try:
            job = require_finished_job(job, user=user)
        except PreviewJobError as e:
            raise HTTPException(e.status_code, e.message) from e

        tables = review_tables_for_job(job)
        if persist_reviews and isinstance(client_tables, list) and client_tables:
            tables = apply_overlay_to_job_reviews(job, client_tables, tables=tables)
            _save_pdf_job(job)
        else:
            overlay_client_tables(tables, client_tables)

        catalog = get_llm_preview_catalog(job)
        needs_catalog = refresh or catalog is None

    if needs_catalog:
        try:
            if force_summarize:
                catalog = await asyncio.to_thread(
                    build_llm_preview_catalog,
                    tables,
                    force_summarize=True,
                    api_key=api_key,
                )
            else:
                catalog = build_llm_preview_catalog(tables, force_summarize=False)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:
            raise HTTPException(502, f"Could not build llm_preview catalog: {e}") from e

        with _pdf_jobs_lock:
            job = _get_pdf_job(job_id)
            if not job_visible_to(job, user):
                raise HTTPException(404, "Job not found")
            set_llm_preview_catalog(job, catalog, source_table_count=len(tables))
            _save_pdf_job(job)
    else:
        assert catalog is not None

    try:
        plan = await asyncio.to_thread(
            plan_from_user_request,
            user_request=user_request,
            catalog=catalog,
            api_key=api_key,
            prompt=prompt,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Could not run llm_input: {e}") from e

    # Re-load live tables after intent so concurrent deletes are reflected.
    with _pdf_jobs_lock:
        job = _get_pdf_job(job_id)
        if not job_visible_to(job, user):
            raise HTTPException(404, "Job not found")
        live_tables = review_tables_for_job(job)
        if not persist_reviews:
            overlay_client_tables(live_tables, client_tables)

    result = execute_action_plan(plan, live_tables)

    action_type = str(result.get("type") or "")
    if confirm_delete and action_type in ("delete", "bulk_delete"):
        to_delete = list(result.get("table_ids") or [])
        if to_delete:
            with _pdf_jobs_lock:
                job = _get_pdf_job(job_id)
                if not job_visible_to(job, user):
                    raise HTTPException(404, "Job not found")
                soft_delete_tables(job, to_delete, save=_save_pdf_job)
            result["executed"] = True
            result["deleted"] = to_delete
            result.pop("message", None)
        else:
            result["executed"] = False

    with _pdf_jobs_lock:
        job = _get_pdf_job(job_id)
        if job_visible_to(job, user):
            append_llm_turn(
                job,
                {
                    "user_request": user_request,
                    "type": result.get("type"),
                    "table_ids": result.get("table_ids") or [],
                    "rationale": result.get("rationale") or "",
                    "executed": result.get("executed"),
                },
            )
            _save_pdf_job(job)

    payload = {**result, "job_id": job_id}
    return LlmInputResponse.model_validate(payload).model_dump()


@router.post("/api/llm_preview/jobs/{job_id}/llm_input")
async def post_llm_input(
    job_id: str,
    request: Request,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Interpret ``user_request`` (LangChain) and return structured Preview actions + ``table_data``."""
    return await _handle_llm_input(job_id, request, user, db)


@router.post("/api/llm_preview/jobs/{job_id}/chat")
async def post_llm_chat(
    job_id: str,
    request: Request,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Alias for ``llm_input`` — single chat entrypoint for steward queries."""
    return await _handle_llm_input(job_id, request, user, db)
