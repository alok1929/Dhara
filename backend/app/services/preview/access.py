"""Job visibility and load helpers shared by PDF Preview and llm_preview."""
from __future__ import annotations

from typing import Any, Optional, Protocol


class PreviewJobError(Exception):
    """Raised when a Preview job cannot be used; ``status_code`` maps to HTTP."""

    def __init__(self, message: str, *, status_code: int = 404):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class _UserLike(Protocol):
    email: str
    organisation_id: Any


def job_visible_to(job: Optional[dict], user: _UserLike) -> bool:
    """Owner email match plus organisation_id when the job is tenant-tagged."""
    if not job or job.get("user_email") != user.email:
        return False
    job_org = job.get("organisation_id")
    if job_org and str(job_org) != str(user.organisation_id):
        return False
    return True


def job_owned_by_email(job: Optional[dict], user_email: str) -> bool:
    return bool(job and job.get("user_email") == user_email)


def require_finished_job(
    job: Optional[dict],
    *,
    user: Optional[_UserLike] = None,
    user_email: Optional[str] = None,
) -> dict:
    """Return job if visible and extraction-complete; else raise PreviewJobError."""
    from app.workers.extraction_jobs import job_extraction_complete

    if user is not None:
        if not job_visible_to(job, user):
            raise PreviewJobError("Job not found", status_code=404)
    elif user_email is not None:
        if not job_owned_by_email(job, user_email):
            raise PreviewJobError("Job not found", status_code=404)
    else:
        if not job:
            raise PreviewJobError("Job not found", status_code=404)

    assert job is not None
    if not job_extraction_complete(job.get("status")):
        raise PreviewJobError(
            f"Job not finished yet (status={job.get('status')})",
            status_code=409,
        )
    return job


# Console pipeline: 1 Files → 2 Preview → 3 Grouping → 4 Metadata → 5 Classify → 6 Publish
PREVIEW_PIPELINE_STEP = 2


def effective_pipeline_step(job: Optional[dict]) -> Optional[int]:
    """
    Console step for UI routing (1 Files … 6 Publish).

    For llm_preview catalog responses we always expose Preview (2) — see
    ``preview_pipeline_step``. This helper is for general job inference.
    """
    if not job:
        return None
    raw = job.get("pipeline_step")
    try:
        if raw is not None:
            return int(raw)
    except (TypeError, ValueError):
        pass

    status = str(job.get("status") or "")
    if status in ("queued", "running", "processing", "error", "failed"):
        return 1

    from app.workers.extraction_jobs import job_extraction_complete

    if job_extraction_complete(status):
        return PREVIEW_PIPELINE_STEP
    return None


def preview_pipeline_step(_job: Optional[dict] = None) -> int:
    """llm_preview sits on the Preview stage — always step 2."""
    return PREVIEW_PIPELINE_STEP


def ensure_preview_pipeline_step(job: dict) -> int:
    """
    Stamp Preview (2) on the job when unset so chat/guided handoff shares
    the same stage. Does not advance past Preview based on grouping.
    """
    if job.get("pipeline_step") is None:
        job["pipeline_step"] = PREVIEW_PIPELINE_STEP
    return PREVIEW_PIPELINE_STEP
