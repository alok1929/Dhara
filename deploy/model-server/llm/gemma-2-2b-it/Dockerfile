# Gemma 2 2B Instruct on the vLLM CPU image.
#
# vllm/vllm-openai-cpu:v0.27.1 is a Linux multi-arch image (amd64 and arm64).
# It does not use a GPU. SERVED_NAME must match this folder, models.yaml,
# and DHARA_LLM_MODEL. Native context is 8192; a higher MAX_MODEL_LEN will
# not start.
#
# Accept the Gemma license on Hugging Face first. Gated weights need
# HUGGING_FACE_HUB_TOKEN (LLM_HF_TOKEN in compose). Weights download into
# the hf_cache volume on first start.
FROM vllm/vllm-openai-cpu:v0.27.1

ENV MODEL_ID=google/gemma-2-2b-it \
    SERVED_NAME=gemma-2-2b-it \
    PORT=8003 \
    MAX_MODEL_LEN=8192 \
    MAX_NUM_SEQS=2 \
    VLLM_CPU_KVCACHE_SPACE=4 \
    VLLM_CPU_OMP_THREADS_BIND=auto

# bfloat16 is the stable CPU dtype. This image has no GPU memory flag.
ENV EXTRA_ARGS="--dtype bfloat16"

EXPOSE 8003
ENTRYPOINT ["sh", "-c", "exec vllm serve $MODEL_ID \
  --served-model-name $SERVED_NAME \
  --host 0.0.0.0 --port $PORT \
  --max-model-len $MAX_MODEL_LEN \
  --max-num-seqs $MAX_NUM_SEQS \
  $EXTRA_ARGS"]
