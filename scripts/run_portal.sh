#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8101}"
exec "$PYTHON" -m uvicorn portal_app:app --host "$HOST" --port "$PORT"
