from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from . import __version__
from .constants import JUNK_EXTENSIONS, SIDECAR_EXTENSIONS, TEXT_JUNK_EXTENSIONS, VIDEO_EXTENSIONS
from .executor import execute_plan, rollback_run
from .llm import suggest_with_llm
from .models import AppSettings, ExecuteRequest, LLMSuggestRequest, PlanRequest, ScanRequest
from .rules import build_plan
from .scanner import scan_files
from .settings_store import get_settings, put_settings

PACKAGE_DIR = Path(__file__).parent

app = FastAPI(title="AVcleaner", version=__version__)
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request, "version": __version__})


@app.get("/api/capabilities")
def capabilities() -> dict:
    return {
        "name": "AVcleaner",
        "version": __version__,
        "platform": "windows-first",
        "features": [
            "scan",
            "preview_plan",
            "rule_rename",
            "llm_suggest",
            "quarantine",
            "execute",
            "rollback",
            "history",
        ],
        "video_extensions": sorted(VIDEO_EXTENSIONS),
        "sidecar_extensions": sorted(SIDECAR_EXTENSIONS),
        "junk_extensions": sorted(JUNK_EXTENSIONS),
        "text_junk_extensions": sorted(TEXT_JUNK_EXTENSIONS),
        "llm_providers": ["openai_compatible", "ollama"],
        "safety": {
            "requires_preview": True,
            "requires_confirm": True,
            "overwrite": False,
            "permanent_delete": False,
            "send_full_path_to_llm_default": False,
        },
    }


@app.get("/api/settings")
def api_get_settings() -> AppSettings:
    return get_settings()


@app.put("/api/settings")
def api_put_settings(settings: AppSettings) -> AppSettings:
    return put_settings(settings)


@app.post("/api/scan")
def api_scan(request: ScanRequest):
    settings = get_settings()
    if request.exclude_dirs is None:
        request.exclude_dirs = settings.exclude_dirs
    if request.extensions is None:
        request.extensions = sorted(
            set(settings.video_extensions) | set(settings.sidecar_extensions) | set(JUNK_EXTENSIONS) | set(TEXT_JUNK_EXTENSIONS)
        )
    try:
        return scan_files(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plan")
def api_plan(request: PlanRequest):
    try:
        return build_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/llm/suggest")
async def api_llm_suggest(request: LLMSuggestRequest):
    try:
        return await suggest_with_llm(request, get_settings().llm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/execute")
def api_execute(request: ExecuteRequest):
    try:
        return execute_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/rollback")
def api_rollback(run_id: str):
    return rollback_run(run_id)


@app.get("/api/runs")
def api_runs():
    from .database import list_runs

    return list_runs()


@app.get("/api/summary")
def api_summary():
    runs = api_runs()
    return {"runs": len(runs), "status": dict(Counter(run.status for run in runs))}
