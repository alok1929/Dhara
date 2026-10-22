"""One OpenAI-compatible chat client, plus JSON salvage logging."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.llm.profiles import LlmProfile

logger = logging.getLogger(__name__)


class LlmClient:
    def __init__(self, profile: LlmProfile) -> None:
        self.profile = profile

    @property
    def kind(self) -> str:
        return self.profile.kind

    @property
    def provider(self) -> str:
        return self.profile.provider

    @property
    def model(self) -> str:
        return self.profile.model

    @property
    def api_key(self) -> str:
        return self.profile.api_key

    @property
    def base_url(self) -> str | None:
        return self.profile.base_url

    @property
    def is_mock(self) -> bool:
        return self.profile.kind == "mock"

    @property
    def is_on_prem(self) -> bool:
        return self.profile.kind == "on-prem"

    def profile_tag(self) -> str:
        return "on-prem" if self.is_on_prem else self.kind

    def openai_sdk(self):
        if self.provider != "openai":
            raise RuntimeError(f"profile {self.kind}/{self.provider} is not OpenAI-compatible")
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": self.api_key or "local"}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return OpenAI(**kwargs)

    def anthropic_sdk(self):
        if self.provider != "anthropic":
            raise RuntimeError(f"profile {self.kind}/{self.provider} is not Anthropic")
        import anthropic

        return anthropic.Anthropic(api_key=self.api_key)

    def langchain_chat(self, *, temperature: float = 0):
        """LangChain chat model pointed at this profile (OpenAI-compat only)."""
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "api_key": self.api_key or "local",
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return ChatOpenAI(**kwargs)

    def completion_text(self, message: Any) -> str:
        """Prefer ``content``. If a reasoning model left it empty, use reasoning text.

        Qwen3.5 on vLLM can put the answer in ``reasoning_content`` while
        ``content`` stays blank. Callers that parse JSON need the text either way.
        """
        content = _message_content(message)
        if content.strip():
            return content
        reasoning = getattr(message, "reasoning_content", None) or getattr(
            message, "reasoning", None
        )
        if reasoning and str(reasoning).strip():
            logger.info(
                "llm empty content; using reasoning_content profile=%s",
                self.profile_tag(),
            )
            return str(reasoning)
        return content

    def loads_json(self, text: str | None, *, context: str) -> Any:
        """Parse JSON. On failure, strip fences and log the profile (on-prem included)."""
        raw = text or ""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "llm json salvage profile=%s context=%s",
                self.profile_tag(),
                context,
            )
            cleaned = re.sub(r"```[a-z]*\n?", "", raw).strip().rstrip("`").strip()
            return json.loads(cleaned)


def _message_content(message: Any) -> str:
    content = getattr(message, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or ""))
            else:
                parts.append(str(getattr(part, "text", "") or ""))
        return "".join(parts)
    return str(content)
