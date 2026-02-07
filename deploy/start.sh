#!/usr/bin/env sh
set -eu

uv run uvicorn service.api:app --host 0.0.0.0 --port 8000 &
api_pid=$!

cleanup() {
    kill "$api_pid" 2>/dev/null || true
    wait "$api_pid" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
