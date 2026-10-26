# LLM slot (vLLM only)

Each folder is a **Dockerfile**. It is not a FastAPI app. GPU folders use
`vllm/vllm-openai`. `gemma-2-2b-it` uses `vllm/vllm-openai-cpu` (Linux amd64
and arm64, no GPU). The published URL is the gateway (`:8100`). This
container listens on `:8003` inside the Compose network.

Default catalogue id: `phi-4-mini-instruct` (`microsoft/Phi-4-mini-instruct`, 3.8B).

`gemma-3-4b` is a second GPU folder. `gemma-2-2b-it` is the CPU folder.
Only one of them runs at a time. GPU uses Compose profile `llm`. CPU uses
profile `llm-cpu`. Do not enable both.

## Another checkpoint

Copy an existing folder to a new directory whose name is the catalogue id, then
change `MODEL_ID`, `SERVED_NAME`, and GPU settings. Example:

```text
llm/gemma-2-9b-it/Dockerfile
  MODEL_ID=google/gemma-2-9b-it
  SERVED_NAME=gemma-2-9b-it
```

Add a `ready` entry in `models.yaml`, set `LLM_MODEL` to that folder name, and
rebuild only the `llm` service (or `llm-cpu` for a CPU image). The gateway
does not change. `DHARA_LLM_MODEL` must be that same id. Comparison runs swap
models this way, not in Settings.

## CPU checkpoint

`gemma-2-2b-it` is Gemma 2 2B Instruct (`google/gemma-2-2b-it`). Context is
8192. Point the gateway at that id when you start the CPU profile. If `.env`
still has `COMPOSE_PROFILES=llm`, change it to `llm-cpu` first so Compose
does not also start the GPU service.

```bash
LLM_MODEL=gemma-2-2b-it docker compose -f compose.llm-only.yml --profile llm-cpu up -d --build
```

`VLLM_CPU_KVCACHE_SPACE` is GiB of RAM for the KV cache (default 4), in
addition to the weights. Do not raise `VLLM_CPU_MAX_MODEL_LEN` above 8192.

Accept the model license on Hugging Face. Set `LLM_HF_TOKEN` if the repo is gated.
