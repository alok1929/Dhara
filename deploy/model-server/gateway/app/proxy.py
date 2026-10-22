"""Stream chat completions from vLLM without buffering the body."""

from __future__ import annotations

import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

# Read/write stay open for as long as a completion takes. Connect fails fast
# when vLLM is still loading weights.
TIMEOUT = httpx.Timeout(connect=5.0, read=None, write=None, pool=5.0)

_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


def _forwardable(headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=TIMEOUT,
        limits=httpx.Limits(max_connections=256, max_keepalive_connections=64),
    )


log = logging.getLogger("gateway")


async def forward_http(
    client: httpx.AsyncClient,
    request: Request,
    target_url: str,
    *,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> StreamingResponse:
    """Forward a request to an OpenAI-compatible upstream and stream the response."""
    upstream_req = client.build_request(
        request.method,
        target_url,
        headers=headers if headers is not None else _forwardable(request.headers),
        content=request.stream() if content is None else content,
        params=request.query_params,
    )
    try:
        resp = await client.send(upstream_req, stream=True)
    except httpx.TransportError as exc:
        log.warning("upstream %s unreachable: %s: %s", target_url, type(exc).__name__, exc)
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "5"},
            content={"error": {
                "message": f"model upstream is not reachable: {exc}",
                "type": "upstream_unreachable",
            }},
        )
    return StreamingResponse(
        resp.aiter_raw(),
        status_code=resp.status_code,
        headers=_forwardable(resp.headers),
        background=BackgroundTask(resp.aclose),
    )
