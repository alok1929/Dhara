# On-prem model server (vLLM)

Dhara does not load model weights. On-prem chat is a **vLLM OpenAI server**
behind **one FastAPI gateway**. Each checkpoint is a Dockerfile under
`deploy/model-server/llm/<catalogue-id>/`, based on `vllm/vllm-openai`.
The gateway is the only URL the API should use. Change
`Dhara/deploy/model-server/` when the checkpoint or proxy changes.

## What runs

| Piece | Process | Port |
|-------|---------|------|
| Gateway | FastAPI reverse proxy | published `:8100` |
| `llm` slot | `vllm serve` (OpenAI API) | internal `:8003` only |

There is not a FastAPI app per model. `compose.llm-only.yml` runs the gateway
and one vLLM container.

Accept the Hugging Face license for the checkpoint you run. Gated repos need
`LLM_HF_TOKEN` (passed through as `HUGGING_FACE_HUB_TOKEN`). First start can
take several minutes while weights download into the `hf_cache` volume;
`/health` stays down until then. Dhara treats a failed or missing chat call
like a missing Settings key and falls back to heuristics.

## Start

```bash
cd deploy/model-server
cp .env.example .env
# set LLM_HF_TOKEN if the model is gated
docker compose -f compose.llm-only.yml --profile llm up -d --build
```

`COMPOSE_PROFILES=llm` (in `.env`) is required or the vLLM service stays off.
The gateway still starts without that profile and answers 503 for chat.

Check the catalogue id:

```bash
curl -s http://127.0.0.1:8100/v1/models
```

The id must appear there. vLLM rejects any other `model` string.

## Id contract

These four strings are the same:

| Place | Example |
|-------|---------|
| Folder `deploy/model-server/llm/<id>/` | `phi-4-mini-instruct` |
| Dockerfile `SERVED_NAME` (`--served-model-name`) | `phi-4-mini-instruct` |
| `models.yaml` → `llm[].id` with `status: ready` | `phi-4-mini-instruct` |
| `DHARA_LLM_MODEL` on the API (and any worker) | `phi-4-mini-instruct` |

`DHARA_LLM_BASE_URL` is the gateway **without** requiring `/v1`
(`http://model-gateway:8100`). The Dhara factory appends `/v1` for the OpenAI SDK.

On a shared Docker network named `dhara_model_net`, the gateway alias is
`model-gateway`. Attach the Dhara `backend` service to that external network
and set:

```bash
DHARA_LLM_BASE_URL=http://model-gateway:8100
DHARA_LLM_MODEL=phi-4-mini-instruct
# optional bearer; vLLM accepts a dummy if the gateway is open
DHARA_LLM_API_KEY=local
```

PDF jobs run in the API process today. If you split a worker container later,
give it the **same** `DHARA_LLM_*` and `DHARA_LLM_PROVIDER` values. Otherwise
chat silently uses the steward key or heuristics.

## Chat vs embeddings

| Mode | Chat | Embeddings |
|------|------|------------|
| On-prem env (`DHARA_LLM_BASE_URL` + `DHARA_LLM_MODEL`) | Gateway → vLLM. User Settings key is ignored for chat. | Settings OpenAI key, or pseudo-embeddings if none |
| Cloud Settings | User key → `api.openai.com` (or Anthropic if that key is Anthropic) | Same OpenAI key when present |
| Neither | Heuristic / skip LLM | Pseudo-embeddings |

Precedence in `app.services.llm.factory`: **mock → on-prem env → Settings key → none**.
`DHARA_LLM_PROVIDER=mock` wins even if the gateway URL is set (tests).

## Two gateways (do not mix them up)

| Story | How it is configured |
|-------|----------------------|
| This model server (vLLM on a GPU) | `DHARA_LLM_BASE_URL`, `DHARA_LLM_MODEL`, optional `DHARA_LLM_API_KEY` |
| MEITY / other OpenAI-compatible cloud | Settings **OpenAI** or **Self-hosted** plus the user's API key. v1 does not store a per-user base URL. Self-hosted still calls the default OpenAI host unless you also set `DHARA_LLM_*` |

A MEITY endpoint is not assumed to be this gateway. Pointing Dhara at vLLM is
an ops env change, not a Settings provider.

## Other checkpoints

The default folder is `llm/phi-4-mini-instruct` (`microsoft/Phi-4-mini-instruct`,
3.8B, context 16384 so a 20 GB GPU can load it). `llm/gemma-3-4b` is a second
ready recipe. A 9B-class model is another folder (see
`deploy/model-server/llm/README.md` and the planned row `gemma-2-9b-it` in
`models.yaml`). Comparison is not a Settings dropdown. Rebuild with a different
`LLM_MODEL`, set `DHARA_LLM_MODEL` to that id, or run
`python scripts/compare_llm_backends.py` against `scripts/fixtures/llm_backends.yaml`.

## Cold start

If the gateway or vLLM is unhealthy, extraction continues with heuristics.
Watch `docker compose -f compose.llm-only.yml logs -f llm` on first boot
instead of assuming the process has hung.
