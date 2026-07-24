#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.tmp/test-venv"

find_python() {
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      if "${candidate}" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
      then
        command -v "${candidate}"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN="$(find_python)" || {
  echo "Python 3.10+ is required because the codebase uses modern type syntax." >&2
  exit 1
}

mkdir -p "${ROOT_DIR}/.tmp"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
PIP_CACHE_DIR="${ROOT_DIR}/.tmp/pip-cache" "${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements.txt"
"${VENV_DIR}/bin/python" -m pytest -q "$@"
