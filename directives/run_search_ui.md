# Run Local Search UI

## Goal

Serve the FastAPI UI and `/api/search` endpoint against the validated local
SQLite FTS5 index.

## Input

- SQLite index: `data/search/drive_search.sqlite`
- Optional Gemini query analyzer: `GEMINI_API_KEY`
- Optional model override: `GEMINI_MODEL` (default: `gemini-3.1-flash-lite`)

## Endpoints

- UI: `GET /`
- Search: `GET /api/search?query=HACCP&limit=20`
- Health: `GET /healthz`

## Required Behavior

1. Validate the SQLite index before starting the server.
2. Open the database read-only for searches.
3. Preserve the existing camelCase API response fields used by the UI.
4. Return HTTP 503 when the index is missing or invalid.
5. Escape file metadata before inserting it into the browser DOM.
6. Send only the user's query to Gemini; obtain all file paths from SQLite.
7. Fall back to deterministic local query cleanup when Gemini is unavailable.

## Run

```bash
./.tmp/test-venv/bin/python execution/run_search_ui.py
```

Then open `http://127.0.0.1:8080`.

To enable Gemini for one local shell session without writing a key to a file:

```bash
read -s GEMINI_API_KEY
export GEMINI_API_KEY
./.tmp/test-venv/bin/python execution/run_search_ui.py
```

## Verification

```bash
curl http://127.0.0.1:8080/healthz
curl --get http://127.0.0.1:8080/api/search \
  --data-urlencode 'query=점검표 ext:pdf tag:품질관리' \
  --data-urlencode 'limit=5'
```
