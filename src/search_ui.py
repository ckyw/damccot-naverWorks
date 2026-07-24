from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse

from src.contextual_search import contextual_search
from src.search_index import index_metadata, validate_index


ROOT_DIR = Path(__file__).resolve().parents[1]


def _index_path() -> Path:
    configured_path = os.getenv("SEARCH_INDEX_PATH")
    return Path(configured_path).expanduser() if configured_path else ROOT_DIR / "data/search/drive_search.sqlite"


def _validate_runtime_index() -> None:
    path = _index_path()
    try:
        validation = validate_index(path)
    except (FileNotFoundError, sqlite3.DatabaseError) as exc:
        raise RuntimeError(f"Search index cannot be opened: {path}") from exc
    if not validation.valid:
        raise RuntimeError(f"Search index validation failed: {validation}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _validate_runtime_index()
    yield


app = FastAPI(title="Damccot Drive Search", lifespan=lifespan)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def search_items(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    return contextual_search(_index_path(), query, limit=limit).as_dict()["results"]


@app.get("/api/search")
def search(query: str = Query(min_length=2, max_length=200), limit: int = Query(default=20, le=50)) -> dict[str, Any]:
    try:
        return contextual_search(_index_path(), query, limit=limit).as_dict()
    except (FileNotFoundError, sqlite3.DatabaseError):
        raise HTTPException(status_code=503, detail="Search index is not available yet.")


@app.get("/healthz")
def healthz(response: Response) -> dict[str, Any]:
    path = _index_path()
    if not path.exists():
        response.status_code = 503
        return {"status": "degraded", "index": "missing"}
    try:
        metadata = index_metadata(path)
    except sqlite3.DatabaseError:
        response.status_code = 503
        return {"status": "degraded", "index": "invalid"}
    return {
        "status": "ok",
        "index": "ready",
        "documents": int(metadata.get("indexed_items", 0)),
        "sources": int(metadata.get("source_count", 0)),
        "queryAnalyzer": "gemini" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "fallback",
    }


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Damccot Drive Finder</title>
<style>
:root{--ink:#18312b;--paper:#f8f4ea;--lime:#dce980;--coral:#f18f6a;--line:#c9c3b5}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 85% 10%,#f8cdb7 0 10%,transparent 30%),var(--paper);color:var(--ink);font-family:Georgia,'Noto Serif KR',serif}.wrap{max-width:920px;margin:0 auto;padding:80px 24px}h1{font-size:clamp(3rem,10vw,6rem);letter-spacing:-.07em;margin:0;line-height:.88}.kicker{font:600 .78rem/1.2 monospace;letter-spacing:.12em;margin-bottom:28px}.lead{max-width:540px;font-size:1.15rem;line-height:1.6;margin:32px 0}form{display:flex;gap:10px;margin:42px 0 20px}input{flex:1;min-width:0;padding:17px;border:1px solid var(--ink);background:#fffdf7;font:1rem inherit}button{border:0;background:var(--ink);color:var(--lime);padding:0 24px;font:600 .9rem monospace;cursor:pointer}.hint{font-size:.85rem;color:#5a6d66}.analysis{margin:28px 0 12px;padding:14px 16px;background:#e8edc4;font:.82rem/1.6 monospace}.group{margin:24px 0 38px;border-top:3px solid var(--ink)}.group-title{padding:14px 0 5px;font:700 .82rem/1.5 monospace;word-break:break-all}.result{border-top:1px solid var(--line);padding:16px 0;display:grid;grid-template-columns:100px 1fr;gap:12px}.type{font:700 .73rem monospace;color:#a84d31}.name{font-size:1.05rem}.path{word-break:break-all;font:.78rem/1.5 monospace;color:#51645e;margin-top:7px}.reason{font:.72rem/1.4 monospace;color:#8a4a36;margin-top:6px}.empty{padding:32px 0;font-size:1.1rem}@media(max-width:600px){.wrap{padding-top:48px}.result{grid-template-columns:1fr}form{display:block}button{width:100%;height:52px;margin-top:10px}}</style></head>
<body><main class="wrap"><div class="kicker">INTERNAL DRIVE FINDER / CONTEXT POC</div><h1>찾고 싶은<br>파일이 있나요?</h1><p class="lead">업무 질문을 그대로 입력하세요. 질의 맥락을 분석한 뒤 관련 폴더와 파일을 함께 찾습니다.</p><form id="search"><input id="q" autofocus placeholder="예: 롯데홈쇼핑에 제출한 원산지 문서는 어디에?" minlength="2"><button>찾기</button></form><div class="hint">민감 폴더는 인덱싱 단계에서 제외됩니다.</div><section id="results"></section></main><script>const f=document.querySelector('#search'),q=document.querySelector('#q'),r=document.querySelector('#results');const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));const item=x=>`<article class="result"><div class="type">${esc(x.isFolder?'FOLDER':x.extension||x.fileType||'FILE')}</div><div><div class="name">${esc(x.fileName||'(이름 없음)')}</div><div class="path">${esc(x.filePath||'')}</div><div class="reason">${esc((x.reasons||[]).join(' · '))}</div></div></article>`;f.onsubmit=async e=>{e.preventDefault();r.innerHTML='<p class="empty">질의를 해석하고 있습니다...</p>';try{const x=await fetch('/api/search?query='+encodeURIComponent(q.value));const d=await x.json();if(!x.ok)throw new Error(d.detail||'검색 요청 실패');const a=d.analysis||{},summary=`<div class="analysis">분석: ${esc(a.cleaned_query||q.value)}<br>핵심 개체: ${esc((a.entities||[]).join(', ')||'없음')} · 주제: ${esc((a.topics||[]).join(', ')||'없음')} · 분석기: ${esc(a.analyzer||'unknown')}</div>`;r.innerHTML=d.groups?.length?summary+d.groups.map(g=>`<section class="group"><div class="group-title">${esc(g.folderPath)} (${g.matchCount})</div>${g.results.map(item).join('')}</section>`).join(''):summary+'<p class="empty">일치하는 경로가 없습니다.</p>'}catch(err){r.innerHTML=`<p class="empty">${esc(err.message)}</p>`}}</script></body></html>"""
