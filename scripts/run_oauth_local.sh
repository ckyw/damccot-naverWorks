#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8080}"
UVICORN_BIN="${UVICORN_BIN:-.venv/bin/uvicorn}"

if [[ ! -x "${UVICORN_BIN}" ]]; then
  echo "Missing ${UVICORN_BIN}. Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
  exit 1
fi

"${UVICORN_BIN}" src.oauth_server:app --reload --host 0.0.0.0 --port "${PORT}"
