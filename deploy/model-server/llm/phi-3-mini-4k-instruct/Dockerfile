# Phi-3 Mini 4k Instruct (3.8B) on the vLLM CPU image.
#
# SERVED_NAME must match this folder, models.yaml, and the Settings id.
# Native context is 4096. A higher MAX_MODEL_LEN will not start.
# The instruct checkpoint ships a chat template. Weights download into
# the hf_cache volume on first start.
FROM vllm/vllm-openai-cpu:v0.27.1

ENV MODEL_ID=microsoft/Phi-3-mini-4k-instruct \
    SERVED_NAME=phi-3-mini-4k-instruct \
    PORT=8003 \
    MAX_MODEL_LEN=4096 \
    MAX_NUM_SEQS=2 \
    VLLM_CPU_KVCACHE_SPACE=4 \
    VLLM_CPU_OMP_THREADS_BIND=auto

# bfloat16 is the stable CPU dtype. This image has no GPU memory flag.
# Phi-3's head size is 96. The AMX CPU kernel then rejects the 16-token
# tile (block_size % alignment). The vec16 kernel accepts that tile.
RUN python -c 'from pathlib import Path; p=Path("/opt/venv/lib/python3.12/site-packages/vllm/v1/attention/backends/cpu_attn.py"); t=p.read_text(); old="if head_size is not None and head_size % 32 != 0 and head_size % 16 == 0:"; new="if head_size is not None and head_size % 16 == 0:"; assert old in t, "cpu attn guard missing"; p.write_text(t.replace(old, new, 1))'

ENV EXTRA_ARGS="--dtype bfloat16 --trust-remote-code --block-size 128"

EXPOSE 8003
ENTRYPOINT ["sh", "-c", "exec vllm serve $MODEL_ID \
  --served-model-name $SERVED_NAME \
  --host 0.0.0.0 --port $PORT \
  --max-model-len $MAX_MODEL_LEN \
  --max-num-seqs $MAX_NUM_SEQS \
  $EXTRA_ARGS"]
