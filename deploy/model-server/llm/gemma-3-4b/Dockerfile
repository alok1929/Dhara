# Gemma 3 4B Instruct on vLLM.
#
# There is no Python server in this folder. vLLM's OpenAI image already
# exposes POST /v1/chat/completions, GET /v1/models, and GET /health.
# Dhara talks to the gateway, which proxies to this container on port 8003.
#
# SERVED_NAME must match the catalogue id (models.yaml llm[].id), the folder
# name, and Dhara's DHARA_LLM_MODEL. vLLM rejects any other "model" field.
#
# Context is sized for Dhara PDF JSON prompts, not VoicEra's 8192 voice cap.
# Accept the Gemma license on Hugging Face before the first start. Gated
# weights need HUGGING_FACE_HUB_TOKEN (LLM_HF_TOKEN in compose).
FROM vllm/vllm-openai:v0.27.1

ENV MODEL_ID=google/gemma-3-4b-it \
    SERVED_NAME=gemma-3-4b \
    PORT=8003 \
    MAX_MODEL_LEN=32768 \
    MAX_NUM_SEQS=8 \
    GPU_MEMORY_UTILIZATION=0.90

# No Qwen reasoning parser. Gemma 3 is multimodal; this stack only sends text.
# Leave EXTRA_ARGS empty unless a vLLM flag is required for the checkpoint.
ENV EXTRA_ARGS=""

EXPOSE 8003
ENTRYPOINT ["sh", "-c", "exec vllm serve $MODEL_ID \
  --served-model-name $SERVED_NAME \
  --host 0.0.0.0 --port $PORT \
  --max-model-len $MAX_MODEL_LEN \
  --max-num-seqs $MAX_NUM_SEQS \
  --gpu-memory-utilization $GPU_MEMORY_UTILIZATION \
  ${VLLM_QUANTIZATION:+--quantization $VLLM_QUANTIZATION} \
  $EXTRA_ARGS"]
