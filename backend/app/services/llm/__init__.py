"""OpenAI-compatible chat client. On-prem weights are served by vLLM, not here."""

from app.services.llm.factory import (
    chat_ready,
    get_llm_for_request,
    get_llm_for_user,
    live_openai_chat,
)
from app.services.llm.profiles import LlmProfile, normalize_openai_base_url

__all__ = [
    "LlmProfile",
    "chat_ready",
    "get_llm_for_request",
    "get_llm_for_user",
    "live_openai_chat",
    "normalize_openai_base_url",
]
