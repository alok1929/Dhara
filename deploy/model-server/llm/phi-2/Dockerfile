# Phi-2 (2.7B) on the vLLM CPU image.
#
# vllm/vllm-openai-cpu:v0.27.1 is a Linux multi-arch image (amd64 and arm64).
# SERVED_NAME must match this folder, models.yaml, and the Settings id.
# Native context is 2048. A higher MAX_MODEL_LEN will not start.
# Phi-2 ships without a chat template, so /v1/chat/completions uses the
# Instruct/Output template copied below. Weights download into the hf_cache
# volume on first start.
FROM vllm/vllm-openai-cpu:v0.27.1

ENV MODEL_ID=microsoft/phi-2 \
    SERVED_NAME=phi-2 \
    PORT=8003 \
    MAX_MODEL_LEN=2048 \
    MAX_NUM_SEQS=2 \
    VLLM_CPU_KVCACHE_SPACE=2 \
    VLLM_CPU_OMP_THREADS_BIND=auto

COPY chat_template.jinja /opt/phi2-chat.jinja

# bfloat16 is the stable CPU dtype. This image has no GPU memory flag.
ENV EXTRA_ARGS="--dtype bfloat16 --chat-template /opt/phi2-chat.jinja"

EXPOSE 8003
ENTRYPOINT ["sh", "-c", "exec vllm serve $MODEL_ID \
  --served-model-name $SERVED_NAME \
  --host 0.0.0.0 --port $PORT \
  --max-model-len $MAX_MODEL_LEN \
  --max-num-seqs $MAX_NUM_SEQS \
  $EXTRA_ARGS"]
