# LLM slot (vLLM only)

Each folder is a **Dockerfile** for `vllm/vllm-openai`. It is not a FastAPI app.
The published URL is the gateway (`:8100`). This container listens on `:8003`
inside the Compose network.

Default catalogue id: `phi-4-mini-instruct` (`microsoft/Phi-4-mini-instruct`, 3.8B).

`gemma-3-4b` is a second ready folder. Only one of them runs at a time.

## Another checkpoint

Copy an existing folder to a new directory whose name is the catalogue id, then
change `MODEL_ID`, `SERVED_NAME`, and GPU settings. Example:

```text
llm/gemma-2-9b-it/Dockerfile
  MODEL_ID=google/gemma-2-9b-it
  SERVED_NAME=gemma-2-9b-it
```

Add a `ready` entry in `models.yaml`, set `LLM_MODEL` to that folder name, and
rebuild only the `llm` service. The gateway does not change. `DHARA_LLM_MODEL`
must be that same id. Comparison runs swap models this way, not in Settings.

Accept the model license on Hugging Face. Set `LLM_HF_TOKEN` if the repo is gated.
