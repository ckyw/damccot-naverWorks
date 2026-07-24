# Damccot Naver Works Shared Drive Tree Collector

Lightweight Python POC for collecting Damccot Naver Works Shared Drive folder and file metadata.

This project does not download or parse original files. It only collects tree metadata such as folder names, file names, paths, types, timestamps, file sizes, and permission metadata.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with Naver Works runtime values:

```env
NAVER_WORKS_ACCESS_TOKEN=
NAVER_WORKS_SHARED_DRIVE_ID=
NAVER_WORKS_ROOT_FILE_ID=
OUTPUT_DIR=./data/sources/SOURCE_NAME
MAX_DEPTH=
COLLECTION_MODE=full
REQUEST_SLEEP_SECONDS=0.2
LOG_LEVEL=INFO
```

### Load `.env` for Shell Commands

Python commands load `.env` automatically. Before running `curl` or other shell commands that reference values such as `$NAVER_WORKS_ACCESS_TOKEN`, load and export the file in the current terminal:

```bash
set -a
source .env
set +a
```

### Automatic Access Token Refresh

Do not keep replacing `NAVER_WORKS_ACCESS_TOKEN` manually. Set `NAVER_WORKS_REFRESH_TOKEN`, `NAVER_WORKS_CLIENT_ID`, and `NAVER_WORKS_CLIENT_SECRET`; the collector then requests a fresh Access Token in memory before collection and retries once after a 401 response.

For Cloud Run, store `NAVER_WORKS_CLIENT_SECRET` and `NAVER_WORKS_REFRESH_TOKEN` in Google Secret Manager, then inject them as environment variables. Do not store the short-lived Access Token in Secret Manager.

```bash
gcloud secrets create naver-works-client-secret --replication-policy=automatic
printf '%s' 'YOUR_CLIENT_SECRET' | gcloud secrets versions add naver-works-client-secret --data-file=-

gcloud secrets create naver-works-refresh-token --replication-policy=automatic
printf '%s' 'YOUR_REFRESH_TOKEN' | gcloud secrets versions add naver-works-refresh-token --data-file=-
```

Grant the Cloud Run runtime service account read access, then deploy with the two secrets mounted as environment variables:

```bash
gcloud secrets add-iam-policy-binding naver-works-client-secret \
  --member="serviceAccount:YOUR_RUNTIME_SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding naver-works-refresh-token \
  --member="serviceAccount:YOUR_RUNTIME_SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding naver-works-refresh-token \
  --member="serviceAccount:YOUR_RUNTIME_SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretVersionAdder"

gcloud run services update YOUR_SERVICE_NAME \
  --region=asia-northeast3 \
  --update-secrets=NAVER_WORKS_CLIENT_SECRET=naver-works-client-secret:latest,NAVER_WORKS_REFRESH_TOKEN=naver-works-refresh-token:latest \
  --update-env-vars=NAVER_WORKS_REFRESH_TOKEN_SECRET_RESOURCE=projects/YOUR_PROJECT_ID/secrets/naver-works-refresh-token
```

If Refresh Token Rotation is enabled in NAVER WORKS, the collector adds the returned Refresh Token as a new Secret Manager version. The running instance keeps it only in memory; later Cloud Run instances read the latest version. Do not grant broader Secret Manager roles than `secretAccessor` and `secretVersionAdder`.

## Run a 1-depth Test

```bash
python3 -m src.main --max-depth 1 --output-dir data/sources/SOURCE_NAME
```

## Run Unit Tests

```bash
./execution/run_tests.sh
```

## Build and Test the Local Search Index

Build the combined SQLite metadata database and FTS5 index from every source
listed in `config/search/sources.yaml`:

```bash
./.tmp/test-venv/bin/python execution/build_search_index.py
./.tmp/test-venv/bin/python execution/validate_search_index.py
```

The generated database is written to `data/search/drive_search.sqlite`. It is a
derived local artifact and can be rebuilt at any time from the source JSON
files and the versioned taxonomy and synonym rules.

Run representative local searches:

```bash
./.tmp/test-venv/bin/python -m src.search_cli '빙수' --limit 5
./.tmp/test-venv/bin/python -m src.search_cli '사진 type:image' --limit 5
./.tmp/test-venv/bin/python -m src.search_cli '점검표 ext:pdf tag:품질관리'
```

Supported inline filters are `type:`, `ext:`, and `tag:`. Sensitive paths are
excluded before any metadata or FTS row is stored.

Run the local SQLite-backed API and search UI:

```bash
./.tmp/test-venv/bin/python execution/run_search_ui.py
```

Open `http://127.0.0.1:8080`. The service exposes `/api/search` and `/healthz`;
it validates the SQLite index before accepting requests.

Natural-language query understanding is enabled when `GEMINI_API_KEY` is
available to the process. Only the user's query is sent to Gemini; file names
and paths remain in the local SQLite search stage. Without a key or when the
API is unavailable, the service automatically uses deterministic query cleanup.

For the Cloud Run QA deployment, the container includes only
`data/search/drive_search.sqlite`; raw Shared Drive JSON sources are excluded.
Register a Gemini key already exported in the current terminal with:

```bash
./execution/register_gemini_secret.sh
```

Follow `directives/deploy_search_cloud_run.md` for the private deployment and
post-deployment checks.

## Run Full Collection

```bash
python3 -m src.main --full-depth --output-dir data/sources/SOURCE_NAME
```

Leave `NAVER_WORKS_ROOT_FILE_ID` empty to collect from the Shared Drive root. Sensitive folders and their descendants are excluded before output when their names include credential markers such as `아이디비번`, `계정정보`, `password`, `credentials`, or `secret`.

For a very large drive, collect top-level folders into separate
`data/sources/SOURCE_NAME/parts/*` output directories, then merge them into the
source output directory:

```bash
python3 -m src.merge_parts \
  --parts-dir data/sources/SOURCE_NAME/parts \
  --output-dir data/sources/SOURCE_NAME \
  --sharedrive-id YOUR_SHAREDRIVE_ID
```

### Local Collection with Secret Manager

Authenticate once with Application Default Credentials, then run without Access Token, Client Secret, or Refresh Token environment variables:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project naver-sharedrive

python3 -m src.main \
  --full-depth \
  --sharedrive-id @2001000000444899 \
  --client-id YOUR_NAVER_WORKS_CLIENT_ID \
  --gcp-project naver-sharedrive \
  --client-secret-name naver-works-client-secret \
  --refresh-token-name naver-works-refresh-token \
  --output-dir data/sources/quality-management
```

CLI arguments take priority over environment variables:

```bash
python3 -m src.main --max-depth 2 --mode full --output-dir ./data/sources/SOURCE_NAME
```

## Naver Works OAuth Callback

This project also includes a tiny FastAPI callback server for issuing a Naver Works OAuth authorization code and exchanging it for tokens.

### Local Callback Server with ngrok

```bash
./scripts/run_oauth_local.sh
```

In another terminal, expose the local server with ngrok:

```bash
ngrok http 8080
```

ngrok will show an HTTPS forwarding URL like:

```text
https://abc123.ngrok-free.app
```

Set the redirect URI in `.env` to the ngrok HTTPS URL plus `/callback`:

```env
NAVER_WORKS_REDIRECT_URI=https://abc123.ngrok-free.app/callback
```

Register the exact same URL in the Naver Works developer console Redirect URL settings.

Then open:

```text
https://abc123.ngrok-free.app/start
```

Useful endpoints:

- `GET /start`: browser page with the Naver Works authorization link
- `GET /auth-url`: returns the generated authorization URL as JSON
- `GET /callback`: receives `code` from Naver Works without printing the code in the response body
- `POST /exchange`: exchanges `code` for masked token JSON by default

### Cloud Run Deploy

Create a Cloud Run environment file from the example:

```bash
cp cloudrun.env.yaml.example cloudrun.env.yaml
```

Fill in `cloudrun.env.yaml`. For the first deployment, `NAVER_WORKS_REDIRECT_URI` can use a placeholder. After Cloud Run gives you the service URL, update it to:

```text
https://YOUR-CLOUD-RUN-URL/callback
```

Deploy:

```bash
gcloud run deploy damccot-naverworks-oauth \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --env-vars-file cloudrun.env.yaml
```

After deployment:

1. Copy the Cloud Run service URL.
2. Update `NAVER_WORKS_REDIRECT_URI` in `cloudrun.env.yaml` to `https://YOUR-CLOUD-RUN-URL/callback`.
3. Redeploy the service with the same command.
4. Register the same callback URL in the Naver Works developer console.
5. Open `https://YOUR-CLOUD-RUN-URL/start` in a browser.
6. After login/consent, `/callback` will show the authorization `code`.
7. Exchange the code:

```bash
curl -X POST https://YOUR-CLOUD-RUN-URL/exchange \
  -H 'Content-Type: application/json' \
  -d '{"code":"PASTE_AUTHORIZATION_CODE"}'
```

Token values are masked in responses by default. To return an unmasked token for a short manual POC, set `OAUTH_UNMASKED_RESPONSE_TOKEN` in the runtime environment and pass the same value in the `X-OAuth-Response-Token` request header with `"masked": false` in the JSON body:

```bash
curl -X POST https://YOUR-CLOUD-RUN-URL/exchange \
  -H 'Content-Type: application/json' \
  -H 'X-OAuth-Response-Token: YOUR_RESPONSE_TOKEN' \
  -d '{"code":"PASTE_AUTHORIZATION_CODE","masked":false}'
```

For a short POC flow, set `OAUTH_EXCHANGE_ON_CALLBACK: "true"` or open `/callback?...&exchange=true` to exchange the code immediately in the callback response. Callback exchange responses still mask token values; do not leave token-bearing responses exposed longer than necessary.

## Outputs

```text
data/
  sources/
    image-assets/
      raw/sharedrive_tree_raw.json
      batches/
      reports/
    quality-management/
      raw/sharedrive_tree_raw.json
      batches/
      reports/
  search/drive_search.sqlite
```

Raw JSON keeps Naver Works identifiers for traceability. Gemini-facing batch JSON omits sensitive identifiers by default and keeps only name, path, type, extension, modified time, and depth.

## Known Limitations

- This collector does not download file contents.
- It cannot determine actual latest approved files.
- It only infers folder/file purpose from names and paths.
- Numeric image filenames such as `IMG_0001.jpg` cannot be understood without image processing.
- Permission-limited folders may be partially invisible.
- This is not a full RAG implementation yet.

## Next Steps

- Run a 1-depth collection and inspect API response compatibility.
- Tune folder/file classification keywords using real output.
- Add Gemini API-based Markdown index generation later.
- Leave room for Naver Works bot integration, folder link generation, OCR, document parsing, and Cloud Run Job deployment.
