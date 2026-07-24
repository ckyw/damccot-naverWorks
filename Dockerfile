FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SEARCH_INDEX_PATH=/app/data/search/drive_search.sqlite

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY data/search/drive_search.sqlite ./data/search/drive_search.sqlite

CMD ["sh", "-c", "uvicorn src.search_ui:app --host 0.0.0.0 --port ${PORT:-8080}"]
