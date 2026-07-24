# Deploy Search QA Service to Cloud Run

## Goal

Deploy the SQLite-backed search QA UI to the existing private Cloud Run service
without uploading raw NAVER WORKS tree JSON files or exposing the Gemini key.

## Inputs

- Validated SQLite index: `data/search/drive_search.sqlite`
- Secret Manager secret: `gemini-api-key`
- Service: `damccot-naverworks-search`
- Project: `naver-sharedrive`
- Region: `asia-northeast3`

## Preflight

```bash
./execution/run_tests.sh
./.tmp/test-venv/bin/python execution/validate_search_index.py
gcloud secrets versions list gemini-api-key --project=naver-sharedrive
```

## Deploy

```bash
gcloud run deploy damccot-naverworks-search \
  --project=naver-sharedrive \
  --region=asia-northeast3 \
  --source=. \
  --update-secrets=GEMINI_API_KEY=gemini-api-key:latest \
  --set-env-vars=GEMINI_MODEL=gemini-3.1-flash-lite \
  --memory=512Mi \
  --timeout=30 \
  --max-instances=2 \
  --no-allow-unauthenticated
```

Preserve the existing IAP and tester access policy. Do not grant public access
to the service merely to simplify browser testing.

## Verification

1. Confirm the new revision is ready and receives all traffic.
2. Access `/healthz` through the authenticated route.
3. Confirm `documents` is `7811`, `sources` is `2`, and `queryAnalyzer` is
   `gemini`.
4. Submit a contextual search and confirm `analysis.analyzer` is `gemini`.
5. Review Cloud Run logs without printing secret values or authorization
   headers.
