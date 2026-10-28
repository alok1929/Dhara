"""Static chat profiles. Settings does not pick Gemma vs OpenAI in v1."""

from __future__ import annotations

from dataclasses import dataclass


# google/gemma-2-2b-it native context. vLLM rejects input + max_tokens above this.
GEMMA_2B_MODEL = "gemma-2-2b-it"
GEMMA_2B_CONTEXT = 8192
# microsoft/BitNet-b1.58-2B-4T native context. llama-server rejects a longer prompt.
BITNET_B158_2B_MODEL = "bitnet-b1.58-2b"
BITNET_B158_2B_CONTEXT = 4096
# microsoft/phi-2 native context. vLLM rejects a longer prompt.
PHI_2_MODEL = "phi-2"
PHI_2_CONTEXT = 2048
# Phi-3 Mini 4k native context.
PHI_3_MINI_MODEL = "phi-3-mini-4k-instruct"
PHI_3_MINI_CONTEXT = 4096
# CPU copies of the other ready models under 5B. The GPU recipes are longer.
PHI_4_MINI_MODEL = "phi-4-mini-instruct"
PHI_4_MINI_CPU_CONTEXT = 8192
GEMMA_3_4B_MODEL = "gemma-3-4b"
GEMMA_3_4B_CPU_CONTEXT = 8192
SMALL_CPU_CONTEXT = {
    GEMMA_2B_MODEL: GEMMA_2B_CONTEXT,
    BITNET_B158_2B_MODEL: BITNET_B158_2B_CONTEXT,
    PHI_2_MODEL: PHI_2_CONTEXT,
    PHI_3_MINI_MODEL: PHI_3_MINI_CONTEXT,
    PHI_4_MINI_MODEL: PHI_4_MINI_CPU_CONTEXT,
    GEMMA_3_4B_MODEL: GEMMA_3_4B_CPU_CONTEXT,
}
# These checkpoints copy a JSON example and then repeat it. Stage commands
# ask them for one sentence instead.
PLAIN_STAGE_REPLY_MODELS = {BITNET_B158_2B_MODEL, PHI_2_MODEL}


def uses_plain_stage_reply(model: str) -> bool:
    return (model or "").strip() in PLAIN_STAGE_REPLY_MODELS


def gemma_2b_json_response_format(model: str) -> dict[str, str] | None:
    """Skip JSON-schema mode on the small CPU checkpoints.

    Gemma 2 2B's CPU engine turns ``json_object`` into a grammar and then
    calls ``torch.tensor(..., pin_memory=True)``. That raises on a machine
    with no CUDA device and kills the server. BitNet's llama-server is
    given the same plain-text JSON path. Callers still parse JSON from
    the reply text.
    """
    if (model or "").strip() in SMALL_CPU_CONTEXT:
        return None
    return {"type": "json_object"}


def fit_gemma_2b_completion(model: str, prompt: str, requested_output: int) -> tuple[str, int]:
    """Shrink a chat call so a small CPU checkpoint accepts it.

    Gemma 2 2B stays under 8192. BitNet b1.58 2B stays under 4096. Phi-2
    stays under 2048. Other models are unchanged. Token count is estimated
    as one token per character, which is higher than the real count.
    """
    requested = max(1, int(requested_output))
    text = prompt or ""
    context = SMALL_CPU_CONTEXT.get((model or "").strip())
    if context is None:
        return text, requested
    margin = 64
    min_output = min(requested, 256)
    max_input = context - min_output - margin
    if max_input < 1:
        max_input = 1
    if len(text) > max_input:
        text = text[:max_input]
    room = context - len(text) - margin
    if room < 1:
        room = 1
    return text, min(requested, room)


def normalize_openai_base_url(raw: str) -> str:
    """Accept ``http://host:8100`` or ``http://host:8100/v1``; always return ``.../v1``."""
    url = (raw or "").strip().rstrip("/")
    if not url:
        raise ValueError("DHARA_LLM_BASE_URL is empty")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"


@dataclass(frozen=True)
class LlmProfile:
    """One resolved chat target.

    ``kind`` is ``mock``, ``on-prem`` (gateway → vLLM), or ``cloud`` (Settings key).
    ``provider`` is ``mock``, ``openai`` (including vLLM and MEITY OpenAI-compat),
    or ``anthropic`` (cloud only; never used when on-prem env is set).
    """

    kind: str
    provider: str
    model: str
    api_key: str
    base_url: str | None = None
