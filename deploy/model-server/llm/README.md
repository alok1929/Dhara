# LLM slot

Each folder is a **Dockerfile**. It is not a FastAPI app. GPU folders use
`vllm/vllm-openai`. `gemma-2-2b-it` uses `vllm/vllm-openai-cpu` (Linux amd64
and arm64, no GPU). `bitnet-b1.58-2b` uses bitnet.cpp `llama-server` on CPU.
The published URL is the gateway (`:8100`). This container listens on `:8003`
inside the Compose network.

Default catalogue id: `phi-4-mini-instruct` (`microsoft/Phi-4-mini-instruct`, 3.8B).

`gemma-3-4b` is a second GPU folder. `gemma-2-2b-it`, `bitnet-b1.58-2b`,
and `phi-2` are CPU folders and can run together. GPU uses Compose profile
`llm`. CPU uses profile `llm-cpu`. Do not enable both profiles. The GPU
service and Gemma share one container name.

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
does not change. `DHARA_LLM_MODEL` must be that same id when nothing is
chosen in Settings. A model that is already running is chosen in Settings:
the API sends that catalogue id, and the gateway forwards it.

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

`bitnet-b1.58-2b` is Microsoft BitNet b1.58 2B 4T. The weights are the
official I2_S GGUF (`microsoft/BitNet-b1.58-2B-4T-gguf`, file
`ggml-model-i2_s.gguf`). Context is 4096. The same `llm-cpu` command starts
it in `dhara-model-bitnet` while Gemma stays in `dhara-model-llm`. The
gateway default route is `bitnet-b1.58-2b=http://bitnet:8003`. The first
build compiles bitnet.cpp. The first container start downloads the GGUF
into `hf_cache`.

In Settings, choose Gemma 2 2B Instruct, BitNet b1.58 2B, or Phi-2 2.7B.
That choice is the model id sent to the gateway. The other containers stay up.

`phi-2` is Microsoft Phi-2 (`microsoft/phi-2`, 2.7B). Context is 2048. It
runs in `dhara-model-phi-2` on the same CPU profile. The gateway route is
`phi-2=http://phi-2:8003`.

Compare every ready CPU model on the same prompts:

```bash
python scripts/eval_slm.py
```

The JSON report is `scripts/output/slm_eval/latest.json`. A new SLM is included
on the next run when its catalogue row is `status: ready` and `device: cpu`
and the gateway is serving that id. Add a shared task in
`scripts/fixtures/slm_eval_prompts.json`.

Accept the model license on Hugging Face. Set `LLM_HF_TOKEN` if the repo is gated.
