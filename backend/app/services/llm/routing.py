"""Per-user chat routing preferences (cloud API key vs on-prem gateway)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

CHAT_SOURCE_CLOUD = "cloud"
CHAT_SOURCE_ON_PREM = "on_prem"


@dataclass(frozen=True)
class LlmChatRouting:
    chat_source: str = CHAT_SOURCE_CLOUD
    on_prem_model: str | None = None

    def normalized(self) -> LlmChatRouting:
        source = (self.chat_source or CHAT_SOURCE_CLOUD).strip().lower()
        if source not in (CHAT_SOURCE_CLOUD, CHAT_SOURCE_ON_PREM):
            source = CHAT_SOURCE_CLOUD
        model = (self.on_prem_model or "").strip() or None
        return LlmChatRouting(chat_source=source, on_prem_model=model)


_routing_ctx: ContextVar[LlmChatRouting | None] = ContextVar(
    "dhara_llm_routing", default=None
)


def bind_llm_routing(routing: LlmChatRouting | None) -> object:
    return _routing_ctx.set(routing.normalized() if routing else None)


def reset_llm_routing(token: object) -> None:
    _routing_ctx.reset(token)  # type: ignore[arg-type]


def current_llm_routing() -> LlmChatRouting | None:
    return _routing_ctx.get()


@contextmanager
def llm_routing_scope(routing: LlmChatRouting | None):
    """Bind routing for downstream ``get_llm_for_request`` / ``live_openai_chat``."""
    token = bind_llm_routing(routing)
    try:
        yield
    finally:
        reset_llm_routing(token)
