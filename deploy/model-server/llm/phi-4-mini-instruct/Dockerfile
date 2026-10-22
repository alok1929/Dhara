# Microsoft Phi-4-mini-instruct (3.8B) on vLLM.
#
# No application code. vLLM serves /v1/chat/completions, /v1/models, and /health.
# SERVED_NAME must match this folder, models.yaml, and DHARA_LLM_MODEL.
FROM vllm/vllm-openai:v0.27.1

ENV MODEL_ID=microsoft/Phi-4-mini-instruct \
    SERVED_NAME=phi-4-mini-instruct \
    PORT=8003 \
    MAX_MODEL_LEN=16384 \
    MAX_NUM_SEQS=8 \
    GPU_MEMORY_UTILIZATION=0.90

# The checkpoint ships custom modeling code. Context is capped so a 20 GB GPU
# can hold weights plus KV cache; raise MAX_MODEL_LEN when the card is larger.
ENV EXTRA_ARGS="--trust-remote-code"

EXPOSE 8003
ENTRYPOINT ["sh", "-c", "exec vllm serve $MODEL_ID \
  --served-model-name $SERVED_NAME \
  --host 0.0.0.0 --port $PORT \
  --max-model-len $MAX_MODEL_LEN \
  --max-num-seqs $MAX_NUM_SEQS \
  --gpu-memory-utilization $GPU_MEMORY_UTILIZATION \
  ${VLLM_QUANTIZATION:+--quantization $VLLM_QUANTIZATION} \
  $EXTRA_ARGS"]
