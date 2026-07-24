#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-naver-sharedrive}"
SECRET_NAME="gemini-api-key"

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "GEMINI_API_KEY is not set in this terminal." >&2
  exit 1
fi

printf '%s' "${GEMINI_API_KEY}" | gcloud secrets versions add "${SECRET_NAME}" \
  --project="${PROJECT_ID}" \
  --data-file=- >/dev/null

echo "Added a new ${SECRET_NAME} version in project ${PROJECT_ID}."
