#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-damccot-naverworks-oauth}"
REGION="${REGION:-asia-northeast3}"
ENV_FILE="${ENV_FILE:-cloudrun.env.yaml}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy cloudrun.env.yaml.example first." >&2
  exit 1
fi

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --allow-unauthenticated \
  --env-vars-file "${ENV_FILE}"

