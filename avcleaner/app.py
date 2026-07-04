from __future__ import annotations

import secrets as stdlib_secrets
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.requests import Request

from . import __version__
from .constants import JUNK_EXTENSIONS, SIDECAR_EXTENSIONS, TEXT_JUNK_EXTENSIONS, VIDEO_EXTENSIONS
from .enums import IssueCode
from .errors import AppError
from .executor import execute_plan_by_id, rollback_run
from .llm import check_llm_settings, suggest_with_llm
from .models import (
    AppSettings,
    CorpusReportResponse,
    ExecutionSummaryRequest,
    LLMPayloadPreviewRequest,
    LLMSuggestionApplyRequest,
    LLMSuggestionRejectRequest,
    LLMTestRequest,
    PlanExecuteRequest,
    PlanItemPatchRequest,
    PlanLLMSuggestRequest,
    PlanSelectionRequest,
    PlanRequest,
    RuleTestRequest,
    RuleTestResponse,
    ScanRequest,
    SettingsExportResponse,
    SettingsImportRequest,
    SettingsImportResponse,
)
from .llm_review import (
    accept_llm_suggestion,
    build_payload_preview,
    generate_llm_suggestions,
    list_plan_llm_suggestions,
    reject_llm_suggestion,
)
from .planner import (
    build_execution_summary,
    create_plan,
    export_plan_csv,
    export_plan_json,
    patch_plan_item,
    response_from_record,
    update_plan_selection,
    validate_stored_plan,
)
from .repository import create_scan, get_plan, list_runs, mark_interrupted_runs
from .rule_corpus import build_report as build_corpus_report
from .rule_corpus import report_response_payload
from .rules import MAX_RULE_TEST_FILENAME_LENGTH, suggest_name_with_trace
from .scanner import scan_files
from .database import connect, utc_now_iso
from .runtime import directory_writable, is_frozen, runtime_path_info
from .settings_store import effective_llm_api_key, get_settings, preview_settings_import, put_settings, sanitized_settings_payload
from .validators import validate_filename

PACKAGE_DIR = Path(__file__).parent
API_TOKEN = stdlib_secrets.token_urlsafe(32)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    mark_interrupted_runs()
    yield


app = FastAPI(title="AVcleaner", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")


def error_payload(error_code: str, message: str = "") -> dict[str, str]:
    return {"error_code": error_code, "message": message or error_code}


def require_token(x_avcleaner_token: str | None = Header(default=None)) -> None:
    if not x_avcleaner_token:
        raise AppError(IssueCode.API_TOKEN_MISSING, 401)
    if not stdlib_secrets.compare_digest(x_avcleaner_token, API_TOKEN):
        raise AppError(IssueCode.API_TOKEN_INVALID, 403)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_payload(str(exc.error_code), exc.message))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    code = "validation_error"
    if any(error.get("type") == "extra_forbidden" for error in exc.errors()):
        code = str(IssueCode.REQUEST_EXTRA_FIELDS)
    return JSONResponse(status_code=422, content={"error_code": code, "details": exc.errors()})


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {"version": __version__, "api_token": API_TOKEN})


@app.get("/api/capabilities")
def capabilities() -> dict:
    return {
        "name": "AVcleaner",
        "version": __version__,
        "platform": "windows-first",
        "features": [
            "scan",
            "persisted_plan",
            "preview_plan",
            "rule_rename",
            "llm_suggest",
            "rule_trace",
            "rule_test",
            "rule_settings",
            "settings_import_export",
            "corpus_report",
            "llm_payload_preview",
            "llm_suggestion_review",
            "llm_suggestion_cache",
            "llm_accept_reject",
            "llm_provider_compatibility_modes",
            "llm_prompt_json_compat",
            "llm_strict_schema_fixed",
            "llm_error_taxonomy",
            "packaging_ready",
            "release_zip",
            "artifact_manifest",
            "packaged_temp_execution_smoke",
            "portable_mode",
            "appdata_mode",
            "health_check",
            "sidecar_awareness",
            "subtitle_language_suffix_preservation",
            "associated_file_grouping",
            "manual_review",
            "persisted_selection",
            "plan_export",
            "execution_summary",
            "quarantine",
            "execute_by_plan_id",
            "rollback",
            "history",
            "api_token",
            "legacy_execute_disabled",
            "beta_ux_polish",
            "diagnostics_panel",
            "first_run_helper",
            "ui_error_explanations",
            "release_candidate_polish",
            "ui_explanation_coverage",
            "diagnostics_summary",
            "quarantine_reason_explanations",
        ],
        "video_extensions": sorted(VIDEO_EXTENSIONS),
        "sidecar_extensions": sorted(SIDECAR_EXTENSIONS),
        "junk_extensions": sorted(JUNK_EXTENSIONS),
        "text_junk_extensions": sorted(TEXT_JUNK_EXTENSIONS),
        "llm_providers": ["openai_compatible", "ollama"],
        "safety": {
            "requires_preview": True,
            "requires_confirm": True,
            "requires_plan_id": True,
            "requires_plan_hash": True,
            "overwrite": False,
            "permanent_delete": False,
            "send_full_path_to_llm_default": False,
        },
        "capabilities": {
            "rule_settings": True,
            "settings_import_export": True,
            "corpus_report": True,
            "manual_review": True,
            "persisted_selection": True,
            "plan_export": True,
            "execution_summary": True,
            "llm_payload_preview": True,
            "llm_suggestion_review": True,
            "llm_suggestion_cache": True,
            "llm_accept_reject": True,
            "llm_review_stability": True,
            "legacy_llm_suggest_disabled": True,
            "legacy_execute_disabled": True,
            "llm_cache_deterministic": True,
            "llm_provider_compatibility_modes": True,
            "llm_prompt_json_compat": True,
            "llm_strict_schema_fixed": True,
            "llm_error_taxonomy": True,
            "packaging_ready": True,
            "release_zip": True,
            "artifact_manifest": True,
            "packaged_temp_execution_smoke": True,
            "portable_mode": True,
            "appdata_mode": True,
            "health_check": True,
            "beta_ux_polish": True,
            "diagnostics_panel": True,
            "first_run_helper": True,
            "ui_error_explanations": True,
            "release_candidate_polish": True,
            "ui_explanation_coverage": True,
            "diagnostics_summary": True,
            "quarantine_reason_explanations": True,
        },
    }


def _keyring_available() -> bool:
    try:
        import keyring

        keyring.get_keyring()
        return True
    except Exception:
        return False


@app.get("/api/health")
def api_health(_token: None = Depends(require_token)) -> dict:
    paths = runtime_path_info()
    database_ok = False
    try:
        with connect() as conn:
            conn.execute("SELECT 1").fetchone()
        database_ok = True
    except Exception:
        database_ok = False
    templates_ok = (PACKAGE_DIR / "templates" / "index.html").exists()
    static_ok = (PACKAGE_DIR / "static").exists()
    data_writable = directory_writable(paths.data_dir)
    return {
        "ok": database_ok and templates_ok and static_ok and data_writable,
        "version": __version__,
        "mode": paths.mode,
        "data_dir": str(paths.data_dir),
        "logs_dir": str(paths.logs_dir),
        "quarantine_dir": str(paths.quarantine_dir),
        "database_ok": database_ok,
        "templates_ok": templates_ok,
        "static_ok": static_ok,
        "data_dir_writable": data_writable,
        "keyring_ok": _keyring_available(),
    }


def _safe_runtime_path_label(kind: str, mode: str) -> str:
    if mode == "portable":
        return f"<portable>\\{kind}"
    if mode == "appdata":
        if kind == "data":
            return "<LOCALAPPDATA>\\AVcleaner"
        return f"<LOCALAPPDATA>\\AVcleaner\\{kind}"
    return f"<AVCLEANER_DATA_DIR>\\{kind}"


@app.get("/api/diagnostics")
def api_diagnostics(_token: None = Depends(require_token)) -> dict:
    paths = runtime_path_info()
    health = api_health()
    settings = get_settings()
    safe_health = {
        key: value
        for key, value in health.items()
        if key not in {"data_dir", "logs_dir", "quarantine_dir"}
    }
    caps = capabilities()["capabilities"]
    summary = {
        "version": __version__,
        "runtime_mode": paths.mode,
        "packaging_mode": "packaged" if is_frozen() else "source",
        "data_dir_writable": bool(safe_health.get("data_dir_writable")),
        "database_ok": bool(safe_health.get("database_ok")),
        "templates_ok": bool(safe_health.get("templates_ok")),
        "static_ok": bool(safe_health.get("static_ok")),
        "keyring_ok": bool(safe_health.get("keyring_ok")),
        "legacy_execute_disabled": True,
        "generic_llm_suggest_disabled": True,
        "llm_configured": settings.llm.provider != "disabled" and bool(settings.llm.model),
        "send_full_path_default": False,
        "llm_send_full_path": bool(settings.llm.send_full_path),
    }
    return {
        "summary": summary,
        "app": {
            "name": "AVcleaner",
            "version": __version__,
        },
        "runtime": {
            "mode": paths.mode,
            "packaging_mode": "packaged" if is_frozen() else "source",
            "data_dir": _safe_runtime_path_label("data", paths.mode),
            "logs_dir": _safe_runtime_path_label("logs", paths.mode),
            "quarantine_dir": _safe_runtime_path_label("quarantine", paths.mode),
        },
        "health": safe_health,
        "capabilities": caps,
        "endpoint_status": {
            "legacy_execute": "disabled",
            "generic_llm_suggest": "disabled",
        },
        "redaction": {
            "secrets": "redacted",
            "auth_headers": "omitted",
            "llm_payloads": "omitted",
            "local_media_paths": "omitted",
        },
    }


@app.get("/api/settings")
def api_get_settings(_token: None = Depends(require_token)) -> AppSettings:
    return get_settings()


@app.put("/api/settings")
def api_put_settings(settings: AppSettings, _token: None = Depends(require_token)) -> AppSettings:
    return put_settings(settings)


@app.get("/api/settings/export")
def api_export_settings(_token: None = Depends(require_token)) -> SettingsExportResponse:
    return SettingsExportResponse(
        settings=sanitized_settings_payload(get_settings()),
        exported_at=utc_now_iso(),
        app_version=__version__,
        format_version=1,
    )


@app.post("/api/settings/import")
def api_import_settings(request: SettingsImportRequest, _token: None = Depends(require_token)) -> SettingsImportResponse:
    try:
        return preview_settings_import(request.settings, dry_run=request.dry_run)
    except ValidationError as exc:
        raise AppError("settings_import_invalid", 422, "Invalid settings import") from exc


@app.post("/api/scan")
def api_scan(request: ScanRequest, _token: None = Depends(require_token)):
    settings = get_settings()
    if request.exclude_dirs is None:
        request.exclude_dirs = settings.exclude_dirs
    if request.extensions is None:
        request.extensions = sorted(
            set(settings.video_extensions) | set(settings.sidecar_extensions) | set(JUNK_EXTENSIONS) | set(TEXT_JUNK_EXTENSIONS)
        )
    try:
        response = scan_files(request)
        return create_scan(request, response)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plans")
def api_create_plan(request: PlanRequest, _token: None = Depends(require_token)):
    try:
        persisted_rules = get_settings().rules
        return response_from_record(create_plan(request.model_copy(update={"rules": persisted_rules})))
    except (ValueError, KeyError) as exc:
        raise AppError(str(exc), 400) from exc


@app.post("/api/plan")
def api_legacy_plan(request: PlanRequest, _token: None = Depends(require_token)):
    return api_create_plan(request, _token)


@app.get("/api/plans/{plan_id}")
def api_get_plan(plan_id: str, _token: None = Depends(require_token)):
    try:
        return response_from_record(get_plan(plan_id))
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.post("/api/plans/{plan_id}/validate")
def api_validate_plan(plan_id: str, _token: None = Depends(require_token)):
    try:
        return response_from_record(validate_stored_plan(plan_id))
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.patch("/api/plans/{plan_id}/items/{item_id}")
def api_patch_plan_item(plan_id: str, item_id: str, request: PlanItemPatchRequest, _token: None = Depends(require_token)):
    try:
        return patch_plan_item(plan_id, item_id, request.target_name)
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.patch("/api/plans/{plan_id}/selection")
def api_update_plan_selection(plan_id: str, request: PlanSelectionRequest, _token: None = Depends(require_token)):
    try:
        return update_plan_selection(plan_id, request)
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.get("/api/plans/{plan_id}/export.json")
def api_export_plan_json(plan_id: str, _token: None = Depends(require_token)):
    try:
        return export_plan_json(plan_id)
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.get("/api/plans/{plan_id}/export.csv")
def api_export_plan_csv(plan_id: str, _token: None = Depends(require_token)) -> Response:
    try:
        return Response(content=export_plan_csv(plan_id), media_type="text/csv")
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.post("/api/plans/{plan_id}/execution-summary")
def api_execution_summary(plan_id: str, request: ExecutionSummaryRequest, _token: None = Depends(require_token)):
    try:
        return build_execution_summary(plan_id, request)
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.post("/api/rules/test")
def api_rules_test(request: RuleTestRequest, _token: None = Depends(require_token)) -> RuleTestResponse:
    filename = request.filename.strip()
    if not filename:
        raise AppError("filename_required", 400)
    if len(filename) > MAX_RULE_TEST_FILENAME_LENGTH:
        raise AppError("filename_too_long", 400)
    settings = get_settings()
    try:
        rules = type(settings.rules).model_validate({**settings.rules.model_dump(mode="json"), **request.settings_override})
    except ValueError as exc:
        raise AppError("invalid_rule_settings", 422) from exc
    suggestion = suggest_name_with_trace(filename, rules)
    validation_preview = validate_filename(suggestion.suggested_name, Path(filename).suffix)
    return RuleTestResponse(suggestion=suggestion, validation_preview=validation_preview)


@app.get("/api/rules/corpus-report")
def api_rules_corpus_report(_token: None = Depends(require_token)) -> CorpusReportResponse:
    try:
        return CorpusReportResponse.model_validate(report_response_payload(build_corpus_report()))
    except Exception as exc:
        raise AppError("corpus_report_failed", 500, "Corpus report failed") from exc


@app.post("/api/plans/{plan_id}/execute")
def api_execute_plan(plan_id: str, request: PlanExecuteRequest, _token: None = Depends(require_token)):
    try:
        return execute_plan_by_id(plan_id, request)
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.post("/api/execute")
def api_execute_legacy(_token: None = Depends(require_token)):
    raise AppError(IssueCode.LEGACY_EXECUTE_DISABLED, 410)


@app.post("/api/plans/{plan_id}/llm/payload-preview")
def api_llm_payload_preview(plan_id: str, request: LLMPayloadPreviewRequest, _token: None = Depends(require_token)):
    try:
        return build_payload_preview(plan_id, request)
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.post("/api/plans/{plan_id}/llm/suggest")
async def api_plan_llm_suggest(plan_id: str, request: PlanLLMSuggestRequest, _token: None = Depends(require_token)):
    try:
        return await generate_llm_suggestions(plan_id, request)
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.get("/api/plans/{plan_id}/llm/suggestions")
def api_plan_llm_suggestions(plan_id: str, _token: None = Depends(require_token)):
    try:
        return list_plan_llm_suggestions(plan_id)
    except KeyError as exc:
        raise AppError("plan_not_found", 404) from exc


@app.post("/api/plans/{plan_id}/llm/suggestions/{suggestion_id}/accept")
def api_accept_llm_suggestion(
    plan_id: str,
    suggestion_id: str,
    request: LLMSuggestionApplyRequest,
    _token: None = Depends(require_token),
):
    try:
        return accept_llm_suggestion(plan_id, suggestion_id, request)
    except KeyError as exc:
        raise AppError("suggestion_not_found", 404) from exc


@app.post("/api/plans/{plan_id}/llm/suggestions/{suggestion_id}/reject")
def api_reject_llm_suggestion(
    plan_id: str,
    suggestion_id: str,
    request: LLMSuggestionRejectRequest,
    _token: None = Depends(require_token),
):
    try:
        return reject_llm_suggestion(plan_id, suggestion_id, request)
    except KeyError as exc:
        raise AppError("suggestion_not_found", 404) from exc


@app.post("/api/runs/{run_id}/rollback")
def api_rollback(run_id: str, _token: None = Depends(require_token)):
    return rollback_run(run_id)


@app.get("/api/runs")
def api_runs(_token: None = Depends(require_token)):
    return list_runs()


@app.get("/api/summary")
def api_summary(_token: None = Depends(require_token)):
    runs = list_runs()
    return {"runs": len(runs), "status": dict(Counter(str(run.state or run.status) for run in runs))}


@app.post("/api/llm/suggest")
async def api_llm_suggest(_token: None = Depends(require_token)):
    raise AppError(IssueCode.LEGACY_LLM_SUGGEST_DISABLED, 410)


@app.post("/api/llm/test")
async def api_llm_test(request: LLMTestRequest, _token: None = Depends(require_token)):
    app_settings = get_settings()
    settings = request.settings or app_settings.llm
    settings = settings.model_copy(update={"api_key": settings.api_key or effective_llm_api_key(app_settings)})
    return await check_llm_settings(settings)
