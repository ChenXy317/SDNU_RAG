#!/usr/bin/env bash
# 拉起 Qdrant、API、前端，并打开页面。MySQL 和 Ollama 使用本机已有服务。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PAGE_URL="http://127.0.0.1:5173"
API_URL="http://127.0.0.1:8000/openapi.json"
LOG_DIR="${TMPDIR:-/tmp}/rag-project"
mkdir -p "$LOG_DIR"

if [[ ! -f backend/.env ]]; then
  cp .env.example backend/.env
fi

port_listening() {
  local port="$1"
  ss -ltn | awk '{print $4}' | grep -q ":${port}$"
}

wait_http() {
  local url="$1"
  local name="$2"
  local attempt
  for attempt in $(seq 1 60); do
    if curl -fsS -o /dev/null --max-time 2 "$url" 2>/dev/null; then
      return 0
    fi
    sleep 0.5
  done
  echo "${name} 没有在预期时间内就绪：${url}" >&2
  return 1
}

start_background() {
  local log_file="$1"
  shift
  setsid "$@" >"$log_file" 2>&1 < /dev/null &
}

if ! mysql -uroot -e "SELECT 1" >/dev/null 2>&1; then
  echo "MySQL 没有响应。请先启动本机 MySQL。" >&2
  exit 1
fi

if ! curl -fsS -o /dev/null --max-time 2 http://127.0.0.1:11434/api/tags; then
  echo "Ollama 没有响应。请先启动本机 Ollama。" >&2
  exit 1
fi

echo "启动 Qdrant"
docker compose up -d
wait_http "http://127.0.0.1:6333/" "Qdrant"

if port_listening 8000; then
  echo "API 已在 8000"
else
  echo "启动 API :8000"
  if [[ ! -d backend/.venv ]]; then
    (cd backend && uv sync)
  fi
  start_background "$LOG_DIR/api.log" \
    uv run --directory "$ROOT/backend" \
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
fi

if port_listening 5173; then
  echo "页面已在 5173"
else
  echo "启动页面 :5173"
  if [[ ! -d frontend/node_modules ]]; then
    (cd frontend && npm install)
  fi
  start_background "$LOG_DIR/web.log" \
    npm --prefix "$ROOT/frontend" run dev -- --host 127.0.0.1 --port 5173
fi

if ! wait_http "$API_URL" "API"; then
  echo "---- API 日志 ----" >&2
  tail -n 40 "$LOG_DIR/api.log" >&2 || true
  exit 1
fi

if ! wait_http "$PAGE_URL" "页面"; then
  echo "---- 页面日志 ----" >&2
  tail -n 40 "$LOG_DIR/web.log" >&2 || true
  exit 1
fi

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$PAGE_URL" >/dev/null 2>&1 || true
fi

echo "页面：${PAGE_URL}"
echo "日志：${LOG_DIR}/api.log  ${LOG_DIR}/web.log"
