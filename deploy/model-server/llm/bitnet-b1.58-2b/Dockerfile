# BitNet b1.58 2B 4T on CPU.
#
# vLLM cannot load the I2_S weights, so this image builds bitnet.cpp and
# serves the official GGUF with llama-server. SERVED_NAME must match this
# folder, models.yaml, and DHARA_LLM_MODEL. Native context is 4096.
#
# The GGUF is public (microsoft/BitNet-b1.58-2B-4T-gguf). First container
# start downloads ggml-model-i2_s.gguf into the hf_cache volume.
FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang \
        cmake \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/BitNet
RUN git clone --depth 1 https://github.com/microsoft/BitNet.git . \
    && git submodule update --init --recursive

# Compile llama-server only. The GGUF is fetched on first start so rebuilds
# do not re-download the weights. Kernel generation uses the model-dir name.
RUN python -m pip install --no-cache-dir huggingface_hub \
    && python - <<'PY'
import sys
from pathlib import Path

import setup_env

sys.argv = [
    "setup_env.py",
    "-md",
    "models/BitNet-b1.58-2B-4T",
    "-q",
    "i2_s",
    "-ld",
    "logs",
]
setup_env.args = setup_env.parse_args()
Path(setup_env.args.log_dir).mkdir(parents=True, exist_ok=True)
setup_env.setup_gguf()
setup_env.gen_code()
setup_env.compile()
PY

ENV MODEL_ID=microsoft/BitNet-b1.58-2B-4T-gguf \
    MODEL_FILE=ggml-model-i2_s.gguf \
    SERVED_NAME=bitnet-b1.58-2b \
    PORT=8003 \
    MAX_MODEL_LEN=4096 \
    BITNET_THREADS=4 \
    MODEL_DIR=/root/.cache/huggingface/bitnet

COPY entrypoint.sh /opt/bitnet-entrypoint.sh
RUN chmod +x /opt/bitnet-entrypoint.sh

EXPOSE 8003
ENTRYPOINT ["/opt/bitnet-entrypoint.sh"]
