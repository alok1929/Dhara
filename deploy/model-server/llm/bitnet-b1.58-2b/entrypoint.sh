#!/bin/sh
# Download the official I2_S GGUF on first start, then serve OpenAI chat.
set -eu

MODEL_DIR="${MODEL_DIR:-/root/.cache/huggingface/bitnet}"
MODEL_FILE="${MODEL_FILE:-ggml-model-i2_s.gguf}"
DEST="${MODEL_DIR}/${MODEL_FILE}"
mkdir -p "$MODEL_DIR"

if [ ! -s "$DEST" ]; then
  python - <<'PY'
import os
from huggingface_hub import hf_hub_download

hf_hub_download(
    repo_id=os.environ["MODEL_ID"],
    filename=os.environ.get("MODEL_FILE", "ggml-model-i2_s.gguf"),
    local_dir=os.environ.get("MODEL_DIR", "/root/.cache/huggingface/bitnet"),
)
PY
fi

SERVER=/opt/BitNet/build/bin/llama-server
if [ ! -x "$SERVER" ]; then
  SERVER=/opt/BitNet/build/bin/server
fi

# Compose sets MAX_MODEL_LEN from the Gemma CPU default (8192). This
# checkpoint's native context is 4096, so a larger value is clamped.
CTX="${MAX_MODEL_LEN:-4096}"
if [ "$CTX" -gt 4096 ]; then
  CTX=4096
fi

exec "$SERVER" \
  -m "$DEST" \
  --host 0.0.0.0 \
  --port "${PORT:-8003}" \
  -c "$CTX" \
  --alias "${SERVED_NAME}" \
  -t "${BITNET_THREADS:-4}"
