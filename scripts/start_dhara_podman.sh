#!/usr/bin/env bash
# Start Dhara (Postgres + API + UI) with Podman Compose and the local model gateway.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE=(podman-compose -f docker-compose.podman.yml)

if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from .env.example"
fi

# Gateway on :8100 (Phi on :8003 via deploy/model-server .env).
if ! curl -sf -m 2 http://127.0.0.1:8100/v1/models >/dev/null; then
  echo "Starting model gateway on :8100..."
  set -a
  # shellcheck source=/dev/null
  source deploy/model-server/.env
  set +a
  export LLM_UPSTREAM="${LLM_UPSTREAM:-http://127.0.0.1:8003}"
  GW_PY="$ROOT/backend/.venv/bin/python"
  if [[ ! -x "$GW_PY" ]]; then
    GW_PY="$(command -v python3)"
  fi
  # Bind 0.0.0.0 so Podman containers reach the gateway via host.containers.internal.
  nohup "$GW_PY" -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8100 --no-access-log \
    --app-dir "$ROOT/deploy/model-server/gateway" \
    >/tmp/dhara-model-gateway.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -sf -m 2 http://127.0.0.1:8100/v1/models >/dev/null && break
    sleep 1
  done
fi

echo "Building and starting Dhara stack (Podman)..."
"${COMPOSE[@]}" up -d --build

echo ""
echo "  UI:       http://localhost:8088"
echo "  API:      http://localhost:8010"
echo "  Docs:     http://localhost:8010/docs"
echo "  Postgres: postgresql://dhara:dhara_local_password@localhost:5434/dhara"
echo "  LLM:      http://127.0.0.1:8100 (phi-4-mini-instruct)"
echo ""
"${COMPOSE[@]}" ps
