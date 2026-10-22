"""Dhara model-server gateway.

The only published port. It proxies OpenAI chat to the vLLM container and
lists the catalogue. It does not load weights.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import catalogue
from .config import Settings, Upstream
from .config import settings as env_settings
from .proxy import _forwardable, forward_http, make_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("gateway")


def conf(request: Request) -> Settings:
    return request.app.state.settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = make_client()
    cloud = app.state.settings.openai
    locals_ = app.state.settings.locals
    if not locals_:
        log.info("llm: not deployed")
    for up in locals_:
        log.info("llm: %s -> %s", up.model, up.url)
    log.info(
        "openai: %s",
        f"{cloud.model} -> {cloud.url}" if cloud.enabled else "not configured",
    )
    yield
    await app.state.http.aclose()


async def _probe(client: httpx.AsyncClient, up: Upstream) -> dict:
    if not up.enabled:
        return {"deployed": False}
    base = {"deployed": True, "model": up.model}
    try:
        response = await client.get(f"{up.url}/health", timeout=2.0)
        return {**base, "reachable": response.status_code == 200}
    except Exception as exc:  # noqa: BLE001
        log.warning("llm health check failed: %s", exc)
        return {**base, "reachable": False}


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Dhara model-server", lifespan=lifespan)
    app.state.settings = settings or env_settings

    @app.get("/health")
    async def health(request: Request):
        client: httpx.AsyncClient = request.app.state.http
        up = conf(request).llm
        check = await _probe(client, up)
        degraded = bool(check.get("deployed") and not check.get("reachable"))
        return JSONResponse(
            status_code=503 if degraded else 200,
            content={
                "status": "degraded" if degraded else "healthy",
                "upstreams": {"llm": check},
            },
        )

    @app.get("/models")
    async def models(request: Request):
        """Every catalogue entry, and whether that id is the one vLLM is serving."""
        up = conf(request).llm
        entries = [
            {**item, "deployed": up.enabled and up.model == item.get("id")}
            for item in catalogue.load()
        ]
        return {
            "object": "list",
            "data": entries,
            "deployed": {"llm": up.model if up.enabled else None},
        }

    @app.get("/v1/models")
    async def list_models(request: Request):
        """OpenAI-compatible list of every model this gateway can call right now."""
        cfg = conf(request)
        data = []
        for up in cfg.locals:
            if up.enabled and up.model:
                data.append({
                    "id": up.model,
                    "object": "model",
                    "owned_by": "dhara",
                })
        if cfg.openai.enabled:
            data.append({
                "id": cfg.openai.model,
                "object": "model",
                "owned_by": "openai",
            })
        return {"object": "list", "data": data}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        """Route by the requested model id. Callers only talk to this gateway."""
        cfg = conf(request)
        body = await request.body()
        model = _requested_model(body)
        if cfg.openai.enabled and model == cfg.openai.model:
            headers = _forwardable(request.headers)
            headers["authorization"] = f"Bearer {cfg.openai.api_key}"
            return await forward_http(
                request.app.state.http,
                request,
                f"{cfg.openai.url}/v1/chat/completions",
                content=body,
                headers=headers,
            )
        local = next((up for up in cfg.locals if up.enabled and model == up.model), None)
        if local is None and model == "" and cfg.llm.enabled:
            local = cfg.llm
        if local is not None:
            return await forward_http(
                request.app.state.http,
                request,
                f"{local.url}/v1/chat/completions",
                content=body,
            )
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": f"model {model!r} is not served by this gateway",
                    "type": "model_not_found",
                }
            },
        )

    return app


def _requested_model(body: bytes) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ""
    if isinstance(payload, dict):
        return str(payload.get("model") or "")
    return ""


app = create_app()
