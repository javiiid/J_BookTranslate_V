"""Local dashboard for J Book Translate; run with ``python -m app.web``."""
from __future__ import annotations

import io
import hashlib
import json
import mimetypes
import shutil
import threading
import traceback
import uuid
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from openai import OpenAI
from app.core.config import (
    DEFAULT_BASE_URL,
    get_openai_config,
    normalize_base_url,
    read_config_safe,
    update_openai_config,
    write_config,
)
from app.core.models import DEFAULT_MODEL, SUPPORTED_MODELS
from app.core.paths import ensure_dir
from app.core.validation import ensure_disk_space, validate_book
from app.core.web_i18n import inject_language_switcher
from app.pipeline.pipeline import translate
from app.output.convert import convert_file, normalize_convert_formats
from app.translation.prompts import get_default_prompt, with_author_voice
from app.storage.database import db
from app.reader.service import chapter_blocks as reader_chapter_blocks, chapters as reader_chapters, chapter as reader_chapter
from app.reader.page import reader_page
from app.welcome.page import welcome_page
from app.account.page import account_page
from app.account.service import (
    account_overview,
    api_keys as account_api_keys,
    create_api_key,
    create_business_request,
    create_order,
    credit_packages,
    install_marketplace_item,
    marketplace as account_marketplace,
    orders as account_orders,
    plans_catalog,
    publisher_overview,
    revoke_api_key,
    start_checkout,
    update_account,
)
from app.library.view import library_page
from app.glossary.service import get_glossary, save_glossary
from app.glossary.automatic import sync_book
from app.jobs.state import _atomic_json
from app.jobs.dashboard import install_jobs_dashboard
from app.jobs.workspace import install_workspace

UTC = timezone.utc
UPLOAD_DIR = ensure_dir("data") / "uploads"
WEB_OUTPUT_DIR = ensure_dir("output") / "web"
JOB_META_DIR = ensure_dir("data") / "jobs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
WEB_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
JOB_META_DIR.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Job:
    id: str
    filename: str
    input_path: Path
    filetype: str
    file_size: int
    options: dict[str, str]
    source_language: str
    target_language: str
    model: str
    mode: str
    status: str = "queued"
    created_at: str = field(default_factory=now)
    started_at: str | None = None
    last_activity: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    pipeline_job_id: str | None = None
    paths: dict | None = None
    log: io.StringIO = field(default_factory=io.StringIO)
    stop_event: threading.Event = field(default_factory=threading.Event)
    output_path: Path | None = None
    error: str | None = None
    cancel_requested: bool = False
    progress: dict[str, int] = field(default_factory=lambda: {"completed": 0, "total": 0})
    assets: dict[str, str] = field(default_factory=dict)
    qa_report: str | None = None
    quality: dict | None = None
    style: str = "literary"


JOBS: dict[str, Job] = {}
CONVERTS: dict[str, dict] = {}
CONVERTS_LOCK = threading.RLock()
JOBS_LOCK = threading.RLock()
RUN_LOCK = threading.Lock()


def _persist_job(job: Job) -> None:
    """Persist web-job metadata so a server restart can recover it."""
    JOB_META_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": job.id, "filename": job.filename, "input_path": str(job.input_path),
        "filetype": job.filetype, "file_size": job.file_size, "options": job.options,
        "source_language": job.source_language, "target_language": job.target_language,
        "model": job.model, "mode": job.mode, "status": job.status,
        "created_at": job.created_at, "started_at": job.started_at,
        "updated_at": job.updated_at, "pipeline_job_id": job.pipeline_job_id,
        "paths": job.paths, "output_path": str(job.output_path) if job.output_path else None,
        "error": job.error, "progress": job.progress,
        "assets": dict(job.assets or {}), "qa_report": job.qa_report,
        "quality": job.quality,
        "style": job.style,
    }
    target = JOB_META_DIR / f"{job.id}.json"
    temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    try:
        db.upsert_job(payload)
    except Exception:
        # SQLite is an observability/index layer; pipeline state remains the
        # authoritative recovery source if the index is temporarily locked.
        pass


def _job_event(job: Job, event: str, message: str, level: str = "INFO") -> None:
    """Record a user-facing job event without affecting translation flow."""
    try:
        db.record_event(job.id, level, event, message, recoverable=level != "ERROR")
    except Exception:
        pass


def _rescue_job(job: Job) -> Path:
    """Create a portable snapshot of all currently recoverable job state."""
    rescue_path = WEB_OUTPUT_DIR / f"{job.id}_rescue.zip"
    candidates = [JOB_META_DIR / f"{job.id}.json", job.input_path]
    if job.output_path:
        candidates.append(job.output_path)
    if job.paths:
        candidates.extend(Path(value) for value in job.paths.values())
    with zipfile.ZipFile(rescue_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        seen = set()
        for candidate in candidates:
            if not candidate.exists():
                continue
            files = candidate.rglob("*") if candidate.is_dir() else [candidate]
            for file_path in files:
                if not file_path.is_file():
                    continue
                resolved = file_path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                archive.write(file_path, f"project/{file_path.name}")
    _job_event(job, "rescue_created", "نسخهٔ نجات پروژه ساخته شد.")
    return rescue_path


def _library_book_for_job(job: Job) -> int | None:
    row = db.fetch_one("SELECT book_id FROM files WHERE job_id=? ORDER BY id LIMIT 1", (job.id,))
    return int(row["book_id"]) if row and row.get("book_id") else None


def _ensure_library_source(job: Job) -> int:
    existing = _library_book_for_job(job)
    if existing:
        return existing
    timestamp = now()
    title = Path(job.filename).stem.replace("_", " ").strip() or job.filename
    book_id = db.execute("INSERT INTO library_books(title, created_at, updated_at) VALUES (?, ?, ?)", (title, timestamp, timestamp))
    db.execute("INSERT INTO files(job_id, book_id, path, kind, display_name, extension, mime_type, language, size_bytes, is_readable, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (job.id, book_id, str(job.input_path), "original", job.filename, job.filetype, mimetypes.guess_type(job.filename)[0] or "application/octet-stream", job.source_language, job.file_size, int(job.filetype == "epub"), timestamp))
    return int(book_id)


def _register_library_output(job: Job) -> None:
    if not job.output_path or not job.output_path.is_file():
        return
    book_id = _ensure_library_source(job)
    digest = hashlib.sha256()
    with job.output_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    timestamp = now()
    db.execute("UPDATE library_books SET updated_at=? WHERE id=?", (timestamp, book_id))
    db.execute("INSERT INTO files(job_id, book_id, path, kind, display_name, extension, mime_type, language, size_bytes, checksum, is_readable, created_at) SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM files WHERE job_id=? AND kind=?)", (job.id, book_id, str(job.output_path), "translated", job.output_path.name, job.filetype, mimetypes.guess_type(job.output_path.name)[0] or "application/octet-stream", job.target_language, job.output_path.stat().st_size, digest.hexdigest(), int(job.filetype == "epub"), timestamp, job.id, "translated"))


def restore_jobs() -> None:
    """Restore jobs from metadata and mark interrupted work resumable."""
    recover = []
    for metadata_path in JOB_META_DIR.glob("*.json"):
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            input_path = Path(data["input_path"])
            if not input_path.exists():
                continue
            job = Job(data["id"], data["filename"], input_path, data["filetype"], data["file_size"],
                data.get("options", {}), data["source_language"], data["target_language"],
                data["model"], data["mode"], data.get("status", "failed"), data.get("created_at", now()),
                data.get("started_at"), data.get("updated_at", now()), data.get("updated_at", now()),
                data.get("pipeline_job_id"), data.get("paths"), io.StringIO(), threading.Event(),
                Path(data["output_path"]) if data.get("output_path") else None, data.get("error"), False,
                data.get("progress", {"completed": 0, "total": 0}),
                assets=data.get("assets") or {}, qa_report=data.get("qa_report"),
                quality=data.get("quality"), style=data.get("style", "literary"))
            was_active = job.status in {"queued", "running"}
            if was_active:
                job.status = "paused" if job.pipeline_job_id else "failed"
                job.error = None if job.pipeline_job_id else "Job stopped before a resumable state was created."
            JOBS[job.id] = job
            try:
                _ensure_library_source(job)
                if job.status == "completed":
                    _register_library_output(job)
            except Exception:
                pass
            if was_active and job.pipeline_job_id and job.filetype == "epub":
                recover.append(job)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
    for job in recover:
        threading.Thread(target=_run_job, args=(job,), kwargs={"resume": True}, daemon=True).start()


def _safe_filename(name: str) -> str:
    return "".join(char if char.isalnum() or char in "._- " else "_" for char in Path(name).name)


def _friendly_error(error: Exception) -> str:
    text = str(error).lower()
    if "missing 'openai" in text or "api configuration" in text or "api_key" in text:
        return "کلید یا Base URL سرویس ترجمه تنظیم نشده است. از پنل کاربری ← تنظیمات سرویس ترجمه آن را وارد کنید."
    if "401" in text or "unauthorized" in text:
        return "کلید Provider پذیرفته نشد (401). این کلید با API Keyهای حساب کاربری تفاوت دارد."
    if "403" in text or "forbidden" in text:
        return "سرویس دسترسی را رد کرد (403). اعتبار حساب، مجوز مدل یا Firewall را بررسی کنید."
    if "404" in text or "not found" in text:
        return "Base URL یا مدل پیدا نشد (404). آدرس سازگار معمولاً باید به /v1 ختم شود."
    if "429" in text or "rate limit" in text:
        return "سقف درخواست‌های API پر شده است؛ کمی بعد دوباره ادامه دهید."
    if "10013" in text or "permissionerror" in text:
        return "ویندوز دسترسی شبکهٔ برنامه را مسدود کرده است (WinError 10013). برنامه را در Firewall مجاز کنید."
    if "timeout" in text or "timed out" in text:
        return "پاسخ Provider بیش از حد طول کشید؛ اینترنت یا وضعیت سرویس را بررسی کنید."
    if "connection" in text or "network" in text:
        return "ارتباط با Provider برقرار نشد. اینترنت، Firewall و Base URL را بررسی کنید."
    return "ترجمه متوقف شد. جزئیات فنی در لاگ در دسترس است."


def _candidate_provider_config(payload: dict) -> tuple[dict[str, str], str]:
    """Build a candidate provider config without mutating the saved config."""
    saved = read_config_safe()
    provider = saved.get("openai", {}) or {}
    base_url = normalize_base_url(payload.get("base_url") or provider.get("base_url") or DEFAULT_BASE_URL)
    api_key = str(payload.get("api_key") or provider.get("api_key") or "").strip()
    model = str(payload.get("default_model") or saved.get("translation", {}).get("default_model") or DEFAULT_MODEL).strip()
    if not api_key:
        raise ValueError("کلید Provider وارد نشده است.")
    return {"api_key": api_key, "base_url": base_url}, model


def _verify_provider_config(config: dict[str, str], model: str) -> dict:
    """Verify connectivity and report whether the selected model is listed."""
    response = OpenAI(**config).models.list()
    model_ids = [str(item.id) for item in (getattr(response, "data", []) or []) if getattr(item, "id", None)]
    return {
        "message": "اتصال سرویس ترجمه برقرار است",
        "base_url": config["base_url"],
        "models": len(model_ids),
        "selected_model": model,
        "model_available": not model_ids or model in model_ids,
    }


def _update_progress(job: Job) -> None:
    if not job.paths:
        return
    try:
        sync_book(db, job.paths)
    except Exception:
        pass
    try:
        previous = (job.progress["completed"], job.progress["total"])
        chunks = Path(job.paths["chunks_file"])
        translations = Path(job.paths["translations_file"])
        if chunks.exists():
            with chunks.open(encoding="utf-8") as file:
                job.progress["total"] = len(json.load(file).get("chunks", []))
        if translations.exists():
            with translations.open(encoding="utf-8") as file:
                job.progress["completed"] = len(json.load(file))
        if previous != (job.progress["completed"], job.progress["total"]):
            job.last_activity = job.updated_at = now()
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        pass


def _on_pipeline_started(job: Job, pipeline_job_id: str, paths: dict) -> None:
    snapshot_path = Path(paths['job_dir']) / 'glossary.json'
    if not snapshot_path.exists():
        _atomic_json(snapshot_path, json.loads(job.options.get('glossary_snapshot', '{}')))
    with JOBS_LOCK:
        job.pipeline_job_id = pipeline_job_id
        job.paths = {key: str(value) for key, value in paths.items()}
        job.started_at = job.started_at or now()
        job.last_activity = job.updated_at = now()
        _persist_job(job)


def _run_job(job: Job, *, resume: bool = False) -> None:
    """Run one job; the lock makes simultaneous translations impossible."""
    with RUN_LOCK, redirect_stdout(job.log), redirect_stderr(job.log):
        try:
            job.status = "running"
            job.started_at = job.started_at or now()
            job.last_activity = job.updated_at = now()
            _persist_job(job)
            _job_event(job, "resumed" if resume else "started", "ترجمه از آخرین نقطهٔ سالم ادامه یافت." if resume else "ترجمه شروع شد.")
            client = OpenAI(**get_openai_config())
            output_name = f"{job.input_path.stem}_{job.options['to_lang'].lower()}_{job.options['model']}.{job.filetype}"
            job.output_path = WEB_OUTPUT_DIR / f"{job.id}_{output_name}"
            prompt = job.options["prompt"] or get_default_prompt(job.options["from_lang"], job.options["to_lang"], job.filetype)
            if job.options.get("preserve_voice", "true") == "true":
                prompt = with_author_voice(prompt)
            mode = "resume" if resume else job.mode
            print(f"Starting web job {job.id}")
            manifest = translate(client=client, input_path=job.input_path, output_path=job.output_path,
                from_lang=job.options["from_lang"], to_lang=job.options["to_lang"], mode=mode,
                model=job.options["model"], fast=mode not in {"batch", "batchcheck", "resumebatch"},
                resume_job_id=job.pipeline_job_id if resume else None, debug=True, filetype=job.filetype,
                output_formats=job.options.get("outputs"), translation_prompt=prompt, stop_event=job.stop_event,
                style_preset=job.style,
                on_job_started=lambda pipeline_id, paths: _on_pipeline_started(job, pipeline_id, paths))
            _update_progress(job)
            job.status = "cancelled" if job.cancel_requested else ("paused" if job.stop_event.is_set() else ("completed" if job.output_path.exists() else "failed"))
            if job.status == "completed":
                _register_library_output(job)
                if manifest:
                    job.assets = {name: str(path) for name, path in (manifest.get("generated") or {}).items()}
                    job.qa_report = manifest.get("qa_report")
                    job.quality = manifest.get("quality")
                    job.style = manifest.get("style", "literary")
            job.last_activity = job.updated_at = now()
            _persist_job(job)
            _job_event(job, job.status, "ترجمه با موفقیت تکمیل شد." if job.status == "completed" else "ترجمه در نقطهٔ امن متوقف شد.")
            if job.status == "paused":
                print("Job paused safely. Use Resume to continue from saved progress.")
        except BaseException as exc:
            _update_progress(job)
            job.status, job.error = "failed", _friendly_error(exc)
            job.last_activity = job.updated_at = now()
            _persist_job(job)
            _job_event(job, "failed", job.error or "ترجمه با خطا متوقف شد.", "ERROR")
            traceback.print_exc()


def _job_payload(job: Job) -> dict:
    _update_progress(job)
    total, completed = job.progress["total"], job.progress["completed"]
    elapsed_seconds = 0
    if job.started_at:
        try: elapsed_seconds = max(0, (datetime.now(UTC) - datetime.fromisoformat(job.started_at)).total_seconds())
        except ValueError: pass
    rate = completed / elapsed_seconds if completed and elapsed_seconds else 0
    eta_seconds = round((total - completed) / rate) if rate and total > completed else 0
    inactive_seconds = 0
    try: inactive_seconds = max(0, (datetime.now(UTC) - datetime.fromisoformat(job.updated_at)).total_seconds())
    except ValueError: pass
    health = "red" if job.status == "failed" or (job.status == "running" and inactive_seconds > 600) else "yellow" if job.status in {"queued", "paused", "stopping"} or (job.status == "running" and inactive_seconds > 120) else "green"
    result = {"id": job.id, "filename": job.filename, "filetype": job.filetype.upper(), "file_size": job.file_size,
        "source_language": job.source_language, "target_language": job.target_language, "model": job.model, "mode": job.mode,
        "status": job.status, "created_at": job.created_at, "started_at": job.started_at, "updated_at": job.updated_at, "last_activity": job.updated_at, "output_path": str(job.output_path) if job.output_path else None,
        "progress": {"completed": completed, "total": total, "percent": round(completed * 100 / total) if total else 0},
        "health": health, "eta_seconds": eta_seconds, "chunks_per_minute": round(rate * 60, 2),
        "log": job.log.getvalue(), "error": job.error,
        "can_stop": job.status == "running" and job.mode != "batch",
        "can_cancel": job.status in {"queued", "running", "paused"},
        "can_resume": job.status in {"paused", "failed"} and bool(job.pipeline_job_id) and job.filetype == "epub"}
    result["rescue"] = f"/downloads/rescue/{job.id}"
    result["assets"] = dict(job.assets or {})
    result["qa_report"] = job.qa_report
    result["quality"] = job.quality
    result["style"] = job.style
    if job.status == "completed" and job.output_path:
        result["download"] = f"/downloads/{job.id}"
        result["asset_downloads"] = {name: f"/downloads/{job.id}/{name}" for name in (job.assets or {})}
        if job.filetype == "epub":
            result["reader"] = f"/reader/{job.id}"
    return result


def dashboard_summary() -> dict:
    """Return the lightweight aggregate used by the future dashboard sidebar."""
    with JOBS_LOCK:
        jobs = list(JOBS.values())
    counts = {
        "active_jobs": sum(job.status in {"queued", "running"} for job in jobs),
        "paused_jobs": sum(job.status == "paused" for job in jobs),
        "completed_jobs": sum(job.status == "completed" for job in jobs),
        "failed_jobs": sum(job.status == "failed" for job in jobs),
        "total_books": len({str(job.input_path) for job in jobs}),
    }
    config = read_config_safe().get("openai", {})
    api_status = "ready" if config.get("api_key") and config.get("base_url") else "not_configured"
    storage_free = shutil.disk_usage(ensure_dir("data")).free
    # Token usage is not persisted by the provider layer yet; returning zero
    # is explicit and avoids presenting an invented cost to the user.
    return {
        **counts,
        "storage_free": storage_free,
        "api_status": api_status,
        "estimated_cost": 0.0,
    }


READING_DEFAULTS = {
    "study_night_mode": False,
    "reading_theme": "light",
    "reading_mode": "translation",
    "reading_font_size": 18,
    "reading_line_height": 1.9,
    "reading_width": 760,
    "reading_direction": "auto",
    "reading_last_location": None,
}


def reading_settings() -> dict:
    values = dict(READING_DEFAULTS)
    for row in db.fetch_all("SELECT key, value_json FROM settings WHERE key LIKE 'reading_%' OR key='study_night_mode'"):
        try:
            values[row["key"]] = json.loads(row["value_json"])
        except (TypeError, json.JSONDecodeError):
            continue
    return values


def library_summary(query: str = "") -> dict:
    params = parse_qs(query)
    search = params.get("q", [""])[0].strip().lower()
    status_filter = params.get("status", [""])[0].strip().lower()
    type_filter = params.get("type", [""])[0].strip().lower()
    archived_mode = status_filter == "archived"
    books = db.fetch_all(f"SELECT * FROM library_books WHERE archived={1 if archived_mode else 0} ORDER BY updated_at DESC")
    items = []
    for book in books:
        if search and search not in book["title"].lower():
            continue
        files = db.fetch_all(f"SELECT * FROM files WHERE book_id=? AND archived={1 if archived_mode else 0} ORDER BY CASE kind WHEN 'translated' THEN 0 ELSE 1 END, id", (book["id"],))
        variants = []
        statuses = []
        for file in files:
            if type_filter and file.get("extension", "").lower() != type_filter.lstrip("."):
                continue
            job = db.fetch_one("SELECT status, progress_completed, progress_total, source_language, target_language, model, error FROM jobs WHERE id=?", (file.get("job_id"),)) if file.get("job_id") else None
            status = (job or {}).get("status") or ("completed" if file["kind"] in {"original", "translated"} else "unknown")
            statuses.append(status)
            variant = {**file, "status": status, "progress": {"completed": (job or {}).get("progress_completed", 0), "total": (job or {}).get("progress_total", 0)}, "error": (job or {}).get("error")}
            if file.get("job_id") and file["kind"] == "translated":
                variant["download"] = f"/downloads/{file['job_id']}"
                if file.get("extension", "").lower() == "epub":
                    variant["reader"] = f"/reader/{file['job_id']}"
                job_object = JOBS.get(file["job_id"])
                assets = dict((job_object.assets or {}) if job_object else {})
                if assets:
                    versions = [{"name": "main", "download": f"/downloads/{file['job_id']}"}]
                    versions += [{"name": name, "download": f"/downloads/{file['job_id']}/{name}"} for name in sorted(assets)]
                    variant["versions"] = versions
            variants.append(variant)
        if not variants:
            continue
        overall = "archived" if archived_mode else ("completed" if any(s == "completed" for s in statuses) else ("running" if any(s in {"queued", "running"} for s in statuses) else ("failed" if any(s == "failed" for s in statuses) else "available")))
        if status_filter and status_filter not in statuses and status_filter != overall:
            continue
        items.append({"id": book["id"], "title": book["title"], "author": book.get("author", ""), "cover_path": book.get("cover_path"), "created_at": book["created_at"], "updated_at": book["updated_at"], "status": overall, "variants": variants, "size_bytes": sum(int(item.get("size_bytes", 0)) for item in variants), "translated": any(item["kind"] == "translated" for item in variants), "readable": any(item.get("reader") for item in variants)})
    total = len(items)
    try: page, limit = max(1, int(params.get("page", [1])[0])), max(1, min(100, int(params.get("limit", [24])[0])))
    except ValueError: page, limit = 1, 24
    start = (page - 1) * limit
    return {"items": items[start:start + limit], "total": total, "page": page, "limit": limit, "storage": {"used": sum(item["size_bytes"] for item in items), "free": shutil.disk_usage(ensure_dir("data")).free}}


PAGE = r'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>J Book Translate</title><style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap');:root{--bg:#f4f7fb;--surface:#fff;--ink:#142033;--muted:#6d7a90;--line:#e3e9f2;--blue:#356df6;--purple:#7257e8;--cyan:#0ca6a6;--green:#08966c;--red:#e24a4a;--shadow:0 18px 55px rgba(38,57,93,.08)}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 8% 0,#e6efff 0,transparent 32%),radial-gradient(circle at 96% 11%,#eee9ff 0,transparent 27%),var(--bg);font:15px Vazirmatn,Segoe UI,Tahoma,sans-serif;color:var(--ink)}.shell{max-width:1180px;margin:auto;padding:34px 22px 62px}.top{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:26px}.brand{display:flex;align-items:center;gap:14px}.logo{width:49px;height:49px;border-radius:15px;display:grid;place-items:center;background:linear-gradient(140deg,var(--blue),var(--purple));color:#fff;font-size:25px;box-shadow:0 9px 24px #506ff466}.brand h1{font-size:22px;margin:0;font-weight:800}.brand p{margin:3px 0 0;color:var(--muted);font-size:13px}.api-pill{display:flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);border-radius:999px;padding:8px 12px;color:var(--muted);font-size:12px;box-shadow:0 4px 16px #26395a0a}.dot{width:8px;height:8px;border-radius:50%;background:#aeb8c7}.dot.ready{background:var(--green);box-shadow:0 0 0 4px #12b9811b}.dot.error{background:var(--red)}.dashboard{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:20px}.card{background:rgba(255,255,255,.92);border:1px solid rgba(224,230,240,.9);border-radius:20px;box-shadow:var(--shadow)}.form-card{padding:27px}.side{display:grid;gap:20px;align-content:start}.side .card{padding:21px}.section-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:23px}.section-title h2{font-size:18px;margin:0}.step{font-size:12px;color:var(--blue);background:#edf3ff;padding:5px 10px;border-radius:999px}.drop{position:relative;border:1.5px dashed #9ab4eb;background:linear-gradient(135deg,#f8faff,#f0f5ff);border-radius:15px;min-height:136px;display:grid;place-items:center;text-align:center;padding:18px;transition:.2s}.drop.drag{border-color:var(--blue);background:#eaf1ff}.drop input{position:absolute;inset:0;width:100%;opacity:0;cursor:pointer}.upload-icon{font-size:28px;color:var(--blue)}.drop strong{display:block;margin:5px 0 3px}.drop small{color:var(--muted)}.file-info{display:none;margin-top:12px;padding:10px 12px;background:#eff8f5;border-radius:9px;color:#166b55;font-size:13px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:13px}label{display:block;font-size:13px;font-weight:700;margin:18px 0 7px}input,select,textarea{width:100%;font:inherit;border:1px solid #d9e1ed;border-radius:10px;padding:10px 12px;background:#fff;color:var(--ink)}input:focus,select:focus,textarea:focus{outline:0;border-color:var(--blue);box-shadow:0 0 0 3px #356df61a}textarea{resize:vertical;min-height:100px}.optional{font-weight:400;color:var(--muted)}.advanced{margin-top:17px}.advanced summary{cursor:pointer;color:var(--blue);font-weight:700;font-size:13px}.check{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px;margin-top:14px}.check input{width:auto;accent-color:var(--blue)}button{border:0;font:700 14px Vazirmatn,Segoe UI,sans-serif;cursor:pointer;border-radius:10px;padding:12px 15px;transition:.15s}button:hover:not(:disabled){filter:brightness(.97);transform:translateY(-1px)}button:disabled{cursor:not-allowed;opacity:.55}.primary{width:100%;margin-top:21px;color:#fff;background:linear-gradient(135deg,var(--blue),#5a62e8);box-shadow:0 10px 20px #4268d338}.secondary{background:#eef3ff;color:#2d5ed4}.danger{background:#fff0f0;color:#ca3636}.intro{display:flex;gap:11px;line-height:1.8;color:#506078;font-size:13px}.intro i{font-style:normal;display:grid;place-items:center;min-width:34px;height:34px;border-radius:10px;background:#eaf1ff;color:var(--blue)}.fact{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--line);font-size:13px}.fact span{color:var(--muted)}.job{display:none;margin-top:20px;padding:23px}.job-head{display:flex;justify-content:space-between;align-items:flex-start;gap:15px}.job-name{font-weight:800;font-size:16px;word-break:break-word}.job-meta{margin-top:4px;color:var(--muted);font-size:12px}.chip{white-space:nowrap;font-size:12px;font-weight:700;border-radius:999px;padding:6px 10px;background:#f0f3f7;color:#687587}.chip.running{background:#eaf1ff;color:#2b62df}.chip.completed{background:#e6f8f1;color:#087d5c}.chip.stopped,.chip.finished{background:#fff5df;color:#a96b00}.chip.failed{background:#fff0f0;color:#c03636}.progress-row{display:flex;justify-content:space-between;margin:21px 0 8px;font-size:13px;font-weight:700}.progress-track{height:10px;background:#e9eef7;border-radius:99px;overflow:hidden}.progress-value{height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,var(--blue),var(--cyan));transition:width .45s}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:16px}.stat{background:#f8faff;border:1px solid #edf1f7;border-radius:11px;padding:10px}.stat span{display:block;color:var(--muted);font-size:11px;margin-bottom:3px}.stat strong{font-size:13px}.job-actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}.job-actions button,.download{padding:9px 12px;text-decoration:none;display:inline-block}.download{border-radius:10px;background:var(--green);color:#fff;font-size:13px;font-weight:700}.error{display:none;margin-top:14px;background:#fff2f2;color:#a93434;border:1px solid #ffd9d9;border-radius:10px;padding:11px;font-size:13px}.logs{margin-top:19px}.logs summary{cursor:pointer;color:var(--muted);font-weight:700;font-size:13px}.logs pre{direction:ltr;text-align:left;white-space:pre-wrap;max-height:280px;overflow:auto;background:#101827;color:#c9f8df;border-radius:11px;padding:13px;font:12px ui-monospace,Consolas,monospace}.small{font-size:12px;color:var(--muted)}@media(max-width:850px){.dashboard{grid-template-columns:1fr}.side{grid-template-columns:1fr 1fr}.top{align-items:flex-start}}@media(max-width:570px){.shell{padding:22px 13px}.top{display:block}.api-pill{display:inline-flex;margin-top:14px}.form-card{padding:19px}.grid2,.side,.stats{grid-template-columns:1fr}.job-head{display:block}.chip{display:inline-block;margin-top:10px}}
</style></head><body><main class="shell"><header class="top"><div class="brand"><div class="logo">文</div><div><h1>J Book Translate</h1><p>داشبورد ترجمهٔ امن EPUB و PDF</p></div></div><div class="api-pill"><i class="dot" id="api-dot"></i><span id="api-status">در حال بررسی تنظیمات API…</span><button class="secondary" id="verify-api" style="padding:5px 9px;font-size:11px">بررسی اتصال</button></div></header><div class="dashboard"><section><div class="card form-card"><div class="section-title"><h2>ترجمهٔ جدید</h2><span class="step">گام ۱ از ۱</span></div><form id="translate-form"><div class="drop" id="drop"><input required type="file" id="book" name="book" accept=".epub,.pdf"><div><div class="upload-icon">⇧</div><strong>کتاب را اینجا رها کنید یا انتخاب کنید</strong><small>فرمت‌های EPUB و PDF تا حداکثر ۱ گیگابایت</small></div></div><div class="file-info" id="file-info"></div><div class="grid2"><div><label>زبان مبدأ</label><select name="from_lang"><option value="EN" selected>انگلیسی</option><option value="FA">فارسی</option><option value="AR">عربی</option><option value="FR">فرانسوی</option><option value="DE">آلمانی</option><option value="ES">اسپانیایی</option><option value="IT">ایتالیایی</option><option value="RU">روسی</option><option value="TR">ترکی</option><option value="ZH">چینی</option><option value="JA">ژاپنی</option><option value="KO">کره‌ای</option></select></div><div><label>زبان مقصد</label><select name="to_lang"><option value="EN">انگلیسی</option><option value="FA" selected>فارسی</option><option value="AR">عربی</option><option value="FR">فرانسوی</option><option value="DE">آلمانی</option><option value="ES">اسپانیایی</option><option value="IT">ایتالیایی</option><option value="RU">روسی</option><option value="TR">ترکی</option><option value="ZH">چینی</option><option value="JA">ژاپنی</option><option value="KO">کره‌ای</option></select></div></div><div class="grid2"><div><label>مدل ترجمه</label><select name="model"><option value="gpt-5.6-luna" selected>gpt-5.6-luna</option><option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite</option></select></div><div><label>حالت اجرا</label><select name="mode"><option value="">سریع (پیشنهادی)</option><option value="batch">Batch</option><option value="pdfbilingual">PDF دوزبانه</option></select></div></div><details class="advanced"><summary>تنظیمات پیشرفته و دستور ترجمه</summary><label>دستور ترجمه <span class="optional">(اختیاری)</span></label><textarea name="prompt" placeholder="خالی بگذارید تا دستور استاندارد برنامه استفاده شود."></textarea><label class="check"><input type="checkbox" name="debug" value="true" checked>نگهداری فایل‌های موقت برای ادامهٔ امن کار</label></details><button class="primary" id="submit" type="submit">شروع ترجمه</button></form></div><section class="card job" id="job"><div class="job-head"><div><div class="job-name" id="job-name"></div><div class="job-meta" id="job-meta"></div></div><span class="chip" id="chip">در انتظار</span></div><div class="progress-row"><span id="progress-label">در حال آماده‌سازی…</span><span id="percent">۰٪</span></div><div class="progress-track"><div class="progress-value" id="progress"></div></div><div class="stats"><div class="stat"><span>Chunk تکمیل‌شده</span><strong id="completed">۰</strong></div><div class="stat"><span>زمان شروع</span><strong id="started">—</strong></div><div class="stat"><span>آخرین فعالیت</span><strong id="activity">—</strong></div></div><div class="error" id="error"></div><div id="quality-box" style="display:none;margin-top:12px;padding:14px;background:#f0f7ff;border:1px solid #356df633;border-radius:12px"><div class="section-title"><h2>گزارش کیفیت</h2></div><div id="quality-content"></div></div><div class="job-actions"><button class="danger" hidden id="stop">توقف امن</button><button class="secondary" hidden id="resume">ادامهٔ ترجمه</button><a class="download" hidden id="download">دریافت خروجی</a></div><details class="logs"><summary>نمایش لاگ فنی</summary><pre id="log"></pre></details></section></section><aside class="side"><div class="card"><div class="section-title"><h2>پیش از شروع</h2></div><div class="intro"><i>✓</i><div>کلید API هرگز به مرورگر ارسال یا در صفحه نمایش داده نمی‌شود. فایل‌ها فقط روی همین دستگاه پردازش می‌شوند.</div></div></div><div class="card"><div class="section-title"><h2>تنظیمات فعال</h2></div><div class="fact"><span>محدودهٔ اجرا</span><strong>فقط محلی</strong></div><div class="fact"><span>ذخیرهٔ پیشرفت</span><strong>بعد از هر chunk</strong></div><div class="fact"><span>ادامهٔ کار</span><strong>برای EPUB</strong></div><p class="small">برای توقف امن، درخواست در حال اجرا تمام و ذخیره می‌شود؛ سپس ترجمه پیش از chunk بعدی متوقف خواهد شد.</p></div></aside></div></main><script>
const $=s=>document.querySelector(s),form=$('#translate-form'),submit=$('#submit'),jobBox=$('#job'),drop=$('#drop'),book=$('#book'),fileInfo=$('#file-info'),apiDot=$('#api-dot'),apiStatus=$('#api-status');let jobId,timer;const fa=n=>new Intl.NumberFormat('fa-IR').format(n||0),date=v=>v?new Intl.DateTimeFormat('fa-IR',{hour:'2-digit',minute:'2-digit',year:'numeric',month:'short',day:'numeric'}).format(new Date(v)):'—',size=n=>n<1024*1024?(n/1024).toFixed(0)+' KB':(n/1024/1024).toFixed(1)+' MB';function fileChanged(){const f=book.files[0];if(!f){fileInfo.style.display='none';return}fileInfo.textContent=`${f.name} · ${f.name.split('.').pop().toUpperCase()} · ${size(f.size)}`;fileInfo.style.display='block'}book.addEventListener('change',fileChanged);['dragenter','dragover'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',e=>{e.preventDefault();if(e.dataTransfer&&e.dataTransfer.files[0]){book.files=e.dataTransfer.files;fileChanged()}});async function health(verify=false){try{const r=await fetch('/api/health'+(verify?'?verify=1':'')),d=await r.json();apiStatus.textContent=d.message;apiDot.className='dot '+(d.status==='ready'?'ready':'error')}catch{apiStatus.textContent='وضعیت API نامشخص است';apiDot.className='dot error'}}$('#verify-api').onclick=()=>health(true);health();form.addEventListener('submit',async e=>{e.preventDefault();if(!book.files[0])return;submit.disabled=true;submit.textContent='در حال ایجاد کار…';try{const r=await fetch('/api/jobs',{method:'POST',body:new FormData(form)}),d=await r.json();if(!r.ok)throw Error(d.error||'ایجاد job ناموفق بود');jobId=d.id;jobBox.style.display='block';$('#error').style.display='none';watch()}catch(err){alert(err.message);submit.disabled=false;submit.textContent='شروع ترجمه'}});async function action(name){if(!jobId)return;const r=await fetch(`/api/jobs/${jobId}/${name}`,{method:'POST'}),d=await r.json();if(!r.ok)alert(d.error||'عملیات انجام نشد');watch()}$('#stop').onclick=()=>action('stop');$('#resume').onclick=()=>action('resume');function render(d){const p=d.progress;$('#job-name').textContent=d.filename;$('#job-meta').textContent=`${d.filetype} · ${size(d.file_size)} · ${d.id}`;$('#chip').textContent={queued:'در صف',running:'در حال ترجمه',stopping:'در حال توقف',stopped:'متوقف شده',completed:'تکمیل شد',finished:'پایان یافت',failed:'خطا'}[d.status]||d.status;$('#chip').className='chip '+d.status;$('#progress').style.width=p.percent+'%';$('#percent').textContent=fa(p.percent)+'٪';$('#progress-label').textContent=p.total?`${fa(p.completed)} از ${fa(p.total)} chunk`:'در حال آماده‌سازی chunkها…';$('#completed').textContent=p.total?`${fa(p.completed)} / ${fa(p.total)}`:fa(p.completed);$('#started').textContent=date(d.started_at);$('#activity').textContent=date(d.last_activity);$('#log').textContent=d.log||'در انتظار شروع…';const error=$('#error');error.textContent=d.error||'';error.style.display=d.error?'block':'none';const ql=document.getElementById('quality-box');if(ql){ql.style.display=d.quality?'block':'none';if(d.quality){document.getElementById('quality-content').innerHTML='<div style="padding:8px 0"><strong>Quality Report</strong><br>Total chunks: '+d.quality.total_chunks+' · Flagged: '+d.quality.flagged_count+' · Average: '+d.quality.average_composite+'</div>'}}$('#stop').hidden=!d.can_stop;$('#resume').hidden=!d.can_resume;const dl=$('#download');dl.hidden=!d.download;if(d.download)dl.href=d.download;const active=['queued','running','stopping'].includes(d.status);if(!active){clearInterval(timer);submit.disabled=false;submit.textContent='شروع ترجمه'}}function watch(){clearInterval(timer);const tick=async()=>{try{const r=await fetch('/api/jobs/'+jobId),d=await r.json();if(!r.ok)throw Error();render(d)}catch{clearInterval(timer)}};tick();timer=setInterval(tick,1000)}
</script></body></html>'''.replace("__DEFAULT_MODEL__", DEFAULT_MODEL)


SIDEBAR_HTML = r'''<style>
.app-sidebar{position:fixed;z-index:10;right:18px;top:18px;bottom:18px;width:250px;padding:18px 14px;background:rgba(255,255,255,.94);border:1px solid #e2e8f2;border-radius:20px;box-shadow:0 18px 55px rgba(38,57,93,.1);display:flex;flex-direction:column;gap:18px}.shell{margin-right:292px;max-width:calc(1180px - 292px)}.side-brand{display:flex;align-items:center;gap:10px;padding:4px 7px 15px;border-bottom:1px solid #e9edf4}.side-brand-mark{width:36px;height:36px;border-radius:11px;display:grid;place-items:center;color:#fff;background:linear-gradient(140deg,#356df6,#7257e8);font-size:18px}.side-brand strong{font-size:14px}.side-brand small{display:block;color:#78859a;font-size:10px;margin-top:2px}.side-nav{display:grid;gap:5px}.side-nav button{width:100%;border:0;background:transparent;color:#69778d;text-align:right;padding:10px 11px;border-radius:9px;font:600 12px Vazirmatn,Segoe UI,sans-serif;cursor:pointer}.side-nav button:hover,.side-nav button.active{background:#edf3ff;color:#2e62dc}.side-nav button span{display:inline-block;width:23px;color:#7890bd;font-size:15px;vertical-align:-2px}.side-section{color:#a0aabd;font-size:10px;font-weight:700;padding:8px 11px 1px}.side-summary{margin-top:auto;padding:13px;border-radius:13px;background:linear-gradient(145deg,#f4f7ff,#f4fbfa);border:1px solid #e8eef8}.side-summary-title{font-size:11px;font-weight:700;margin-bottom:9px}.side-stat{display:flex;justify-content:space-between;padding:5px 0;color:#6c7890;font-size:11px}.side-stat strong{color:#263852}.side-api{display:flex;align-items:center;gap:6px;margin-top:8px;color:#07805e;font-size:10px}.side-dot{width:7px;height:7px;border-radius:50%;background:#aeb8c7}.side-dot.ready{background:#09a174;box-shadow:0 0 0 3px #09a1741a}.side-dot.error{background:#e24a4a}.dashboard-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin-bottom:18px}.dashboard-card{padding:14px;background:#fff;border:1px solid #e5ebf4;border-radius:14px;box-shadow:0 8px 20px rgba(38,57,93,.04)}.dashboard-card label{font-size:11px;color:#7c899c;margin:0 0 7px}.dashboard-card strong{font-size:21px;color:#263b5d}.dashboard-card.blue{border-top:3px solid #356df6}.dashboard-card.orange{border-top:3px solid #e8a137}.dashboard-card.green{border-top:3px solid #08966c}.dashboard-card.red{border-top:3px solid #e24a4a}.summary-strip{display:flex;gap:12px;flex-wrap:wrap;padding:11px 14px;margin-bottom:16px;background:#f8faff;border:1px solid #e8eef7;border-radius:12px;color:#68778d;font-size:11px}.summary-strip b{color:#2e62dc}.sidebar-toast{position:fixed;right:285px;bottom:25px;background:#142033;color:#fff;border-radius:10px;padding:10px 14px;font-size:12px;display:none;z-index:20}@media(max-width:850px){.app-sidebar{position:relative;right:auto;top:auto;bottom:auto;width:auto;margin:0 13px 0;padding:12px;border-radius:15px}.shell{margin-right:auto;max-width:1180px}.side-brand{display:none}.side-nav{display:flex;overflow:auto}.side-nav button{white-space:nowrap;width:auto}.side-section,.side-summary{display:none}.dashboard-cards{grid-template-columns:repeat(2,1fr)}}@media(max-width:480px){.dashboard-cards{grid-template-columns:1fr 1fr}.dashboard-card strong{font-size:17px}}
</style><aside class="app-sidebar" aria-label="ناوبری اصلی"><div class="side-brand"><div class="side-brand-mark">文</div><div><strong>J Book Translate</strong><small>Translation Studio</small></div></div><nav class="side-nav"><button class="active" data-scroll="dashboard-summary"><span>⌂</span>داشبورد</button><button data-scroll="translate-form"><span>＋</span>ترجمهٔ جدید</button><button data-scroll="job"><span>◷</span>Jobهای فعال</button></nav><div class="side-section">مدیریت محتوا</div><nav class="side-nav"><button data-toast="کتابخانه در مرحلهٔ بعد فعال می‌شود"><span>▣</span>کتابخانه</button><button data-toast="Glossary در مرحلهٔ بعد فعال می‌شود"><span>⌘</span>Glossary</button><button data-toast="Analytics در مرحلهٔ بعد فعال می‌شود"><span>◒</span>آمار و هزینه</button></nav><div class="side-summary"><div class="side-summary-title">خلاصهٔ سیستم</div><div class="side-stat"><span>فضای آزاد</span><strong id="sb-storage">—</strong></div><div class="side-stat"><span>هزینهٔ تقریبی</span><strong id="sb-cost">—</strong></div><div class="side-api"><i class="side-dot" id="sb-api-dot"></i><span id="sb-api">در حال بررسی provider…</span></div></div></aside><div class="sidebar-toast" id="sidebar-toast"></div><script>
(function(){const root=document.querySelector('.dashboard'),nav=document.querySelectorAll('.side-nav button[data-scroll]'),toast=document.querySelector('#sidebar-toast');if(root){root.id='dashboard-summary';const cards=document.createElement('div');cards.className='dashboard-cards';cards.innerHTML='<div class="dashboard-card blue"><label>ترجمه‌های فعال</label><strong id="sb-active">۰</strong></div><div class="dashboard-card orange"><label>متوقف‌شده</label><strong id="sb-paused">۰</strong></div><div class="dashboard-card green"><label>تکمیل‌شده</label><strong id="sb-completed">۰</strong></div><div class="dashboard-card red"><label>دارای خطا</label><strong id="sb-failed">۰</strong></div>';root.prepend(cards);const strip=document.createElement('div');strip.className='summary-strip';strip.innerHTML='<span>کتاب‌ها: <b id="sb-books">۰</b></span><span>فضای آزاد: <b id="sb-storage-main">—</b></span><span>Provider: <b id="sb-provider-main">—</b></span><span>هزینه: <b id="sb-cost-main">—</b></span>';root.prepend(strip)}const fa=n=>new Intl.NumberFormat('fa-IR').format(n||0),formatBytes=n=>n>=1073741824?(n/1073741824).toFixed(1)+' GB':(n/1048576).toFixed(0)+' MB';async function refresh(){try{const response=await fetch('/api/dashboard/summary');if(!response.ok)throw Error();const d=await response.json();document.querySelector('#sb-active').textContent=fa(d.active_jobs);document.querySelector('#sb-paused').textContent=fa(d.paused_jobs);document.querySelector('#sb-completed').textContent=fa(d.completed_jobs);document.querySelector('#sb-failed').textContent=fa(d.failed_jobs);document.querySelector('#sb-books').textContent=fa(d.total_books);document.querySelector('#sb-storage').textContent=formatBytes(d.storage_free);document.querySelector('#sb-storage-main').textContent=formatBytes(d.storage_free);document.querySelector('#sb-cost').textContent='$'+Number(d.estimated_cost||0).toFixed(2);document.querySelector('#sb-cost-main').textContent='$'+Number(d.estimated_cost||0).toFixed(2);document.querySelector('#sb-provider-main').textContent=d.api_status==='ready'?'آماده':'تنظیم نشده';document.querySelector('#sb-api').textContent=d.api_status==='ready'?'Provider آماده است':'Provider تنظیم نشده';document.querySelector('#sb-api-dot').className='side-dot '+(d.api_status==='ready'?'ready':'error')}catch{document.querySelector('#sb-api').textContent='خطا در دریافت وضعیت';document.querySelector('#sb-api-dot').className='side-dot error'}}nav.forEach(button=>button.addEventListener('click',()=>{nav.forEach(item=>item.classList.remove('active'));button.classList.add('active');document.getElementById(button.dataset.scroll)?.scrollIntoView({behavior:'smooth',block:'start'})}));document.querySelectorAll('[data-toast]').forEach(button=>button.addEventListener('click',()=>{toast.textContent=button.dataset.toast;toast.style.display='block';setTimeout(()=>toast.style.display='none',2400)}));refresh();setInterval(refresh,5000)})();
</script>'''
PAGE = PAGE.replace("</body>", SIDEBAR_HTML + r'''<style>
@keyframes intro-rise{from{opacity:0;transform:translateY(14px) scale(.985)}to{opacity:1;transform:none}}@keyframes intro-glow{0%,100%{box-shadow:0 0 0 rgba(83,111,167,0)}50%{box-shadow:0 0 34px rgba(83,111,167,.13)}}body.app-intro .top{animation:intro-rise .55s ease both}body.app-intro .form-card{animation:intro-rise .6s .08s ease both}body.app-intro .side .card{animation:intro-rise .55s ease both}body.app-intro .side .card:nth-child(2){animation-delay:.14s}body.app-intro .job{animation:intro-rise .5s ease both}.theme-toggle{display:inline-flex;align-items:center;gap:6px;margin-inline-start:7px;padding:6px 10px!important;border:1px solid var(--line)!important;background:var(--surface)!important;color:var(--ink)!important;border-radius:999px!important;font-size:11px!important}.theme-toggle .theme-icon{font-size:14px}.theme-toggle:hover{transform:none!important;filter:brightness(.96)}body.app-dark{--bg:#17191d;--surface:#22252b;--ink:#d8d2c8;--muted:#aaa69f;--line:#343941;--shadow:0 18px 55px rgba(0,0,0,.22);background:radial-gradient(circle at 8% 0,#242c3d 0,transparent 32%),radial-gradient(circle at 96% 11%,#2b263d 0,transparent 27%),var(--bg)}body.app-dark .card,body.app-dark .app-sidebar{background:rgba(34,37,43,.96);border-color:#343941;box-shadow:var(--shadow)}body.app-dark input,body.app-dark select,body.app-dark textarea{background:#1d2025;color:var(--ink);border-color:#3b424d}body.app-dark .drop{background:linear-gradient(135deg,#252b35,#20252c);border-color:#546b92}body.app-dark .file-info{background:#1c302a;color:#a8dfca}body.app-dark .dashboard-card,body.app-dark .summary-strip,body.app-dark .stat{background:#1d2025;border-color:#343941}body.app-dark .side-nav button{color:#aaaeb8}body.app-dark .side-nav button:hover,body.app-dark .side-nav button.active{background:#29344b;color:#b8caff}body.app-dark .api-pill{background:#22252b;border-color:#343941;color:#aaa69f}body.app-dark .intro,body.app-dark .fact,body.app-dark .small{color:#aaa69f}body.app-dark .logs pre{background:#101216}body.app-dark .secondary{background:#29344b;color:#c1d0ff}body.app-dark .danger{background:#3b2427;color:#ffb7b7}
</style><script>(function(){const body=document.body;body.classList.add('app-intro');const key='jbook-study-dark';const saved=localStorage.getItem(key)==='1';if(saved)body.classList.add('app-dark');const pill=document.querySelector('.api-pill');if(!pill)return;const button=document.createElement('button');button.type='button';button.className='theme-toggle';button.innerHTML='<span class="theme-icon">◐</span><span class="theme-label"></span>';pill.appendChild(button);const sync=()=>{const dark=body.classList.contains('app-dark');button.querySelector('.theme-icon').textContent=dark?'☀':'◐';button.querySelector('.theme-label').textContent=dark?'حالت روشن':'حالت شب';button.setAttribute('aria-pressed',dark)};button.onclick=()=>{body.classList.toggle('app-dark');localStorage.setItem(key,body.classList.contains('app-dark')?'1':'0');sync()};sync();setTimeout(()=>body.classList.remove('app-intro'),1400)})();</script><script>(function(){const routes={'کتابخانه':'/api/library','Glossary':'/api/glossaries','آمار و هزینه':'/api/analytics/overview'};document.querySelectorAll('[data-toast]').forEach(b=>b.addEventListener('click',async()=>{const key=Object.keys(routes).find(k=>b.textContent.includes(k));if(!key)return;try{const d=await (await fetch(routes[key])).json();const t=document.querySelector('#sidebar-toast');t.textContent=key+' · '+(d.items?('تعداد: '+d.items.length):'داده دریافت شد');t.style.display='block';setTimeout(()=>t.style.display='none',3000)}catch{}}));const dl=document.querySelector('#download');if(dl){const reader=document.createElement('a');reader.id='reader-link';reader.className='download';reader.textContent='مطالعه در مرورگر';reader.hidden=true;dl.parentElement.appendChild(reader);const sync=()=>{reader.hidden=dl.hidden||!dl.href;reader.href=dl.href.replace('/downloads/','/reader/')};new MutationObserver(sync).observe(dl,{attributes:true});sync()}})();</script>''' + "</body>")


PAGE = PAGE.replace("</head>", "<style>body.app-dark .side-summary{background:linear-gradient(145deg,#20252d,#202c2b)!important;border-color:#3b4650!important;color:#d8d2c8}body.app-dark .side-summary .side-stat{color:#a9b0bb;border-bottom-color:#343941}body.app-dark .side-summary .side-stat strong{color:#e0d9cd}body.app-dark .side-summary .side-api{color:#83d0b3}body.app-dark .side-summary-title{color:#ece5d9}</style></head>")
PAGE = PAGE.replace("</body>", "<script>document.addEventListener('click',function(event){const button=event.target.closest('[data-toast]');if(button&&button.textContent.includes('کتابخانه')){event.preventDefault();event.stopImmediatePropagation();location.href='/library'}},true);</script></body>")


PAGE = PAGE.replace('<button class="primary" id="submit"', '''<label class="check"><input type="checkbox" name="auto_glossary" value="true" checked>ساخت خودکار واژه‌نامه حین ترجمه</label><p id="auto-glossary-note">برای ثبات اصطلاحات، واژه‌نامهٔ خودکار ترجمه را ترتیبی می‌کند. برای حالت Turbo و ارسال هم‌زمان چند chunk، این گزینه را خاموش کنید.</p><button class="primary" id="submit"''', 1)
PAGE = PAGE.replace('<button class="primary" id="submit"', '''<label class="check"><input type="checkbox" name="preserve_voice" value="true" checked>حفظ لحن و صدای نویسنده</label><button class="primary" id="submit"''', 1)
PAGE = PAGE.replace('<button class="primary" id="submit"', '''<div class="grid2"><div style="grid-column:1/-1"><label>خروجی‌های اضافی پس از ترجمه (اختیاری)</label><div><label class="check"><input type="checkbox" name="outputs" value="json_segments">JSON_SEGMENTS <small>(حافظهٔ ترجمه)</small></label><label class="check"><input type="checkbox" name="outputs" value="txt_bilingual">TXT_BILINGUAL</label><label class="check"><input type="checkbox" name="outputs" value="markdown">MARKDOWN</label><label class="check"><input type="checkbox" name="outputs" value="docx">DOCX</label><label class="check"><input type="checkbox" name="outputs" value="translated_pdf">TRANSLATED_PDF</label><label class="check"><input type="checkbox" name="outputs" value="bilingual_pdf">BILINGUAL_PDF</label><label class="check"><input type="checkbox" name="outputs" value="quality_report">QUALITY_REPORT <small>(امتیاز شش‌بعدی LLM)</small></label><small style="display:block;color:#8892a0;margin-top:4px">سگمنت‌های پرچم‌شده ({NOTE:} / {BOUNDARY_WARNING}) در خروجی‌ها هایلایت شده و در QA_REPORT فهرست می‌شوند.</small></div></div></div><button class="primary" id="submit"''', 1)
PAGE = PAGE.replace('<button class="primary" id="submit"', '''<label style="display:block;margin:8px 0"><strong>سبک ترجمه:</strong>
<select name="style_preset" style="margin-right:8px;padding:6px 10px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font-size:13px">
<option value="literary" selected>📖 ادبی</option>
<option value="technical">⚙️ فنی</option>
<option value="conversational">💬 محاوره‌ای</option>
<option value="formal">🏛️ رسمی</option>
</select></label><button class="primary" id="submit"''', 1)
PAGE = PAGE.replace('</body>', '''<script>(()=>{const mode=document.querySelector('[name="mode"]'),auto=document.querySelector('[name="auto_glossary"]');function sync(){auto.disabled=mode.value==='batch'}mode.addEventListener('change',sync);sync()})();</script></body>''', 1)


CONVERT_CARD_HTML = r'''<div class="card form-card" id="convert-card" style="margin-top:18px"><div class="section-title"><h2>تبدیل سریع فایل</h2><span class="step">بدون ترجمه</span></div><p class="small" style="color:var(--muted);margin:-8px 0 14px;line-height:1.7">فایل EPUB / PDF / SRT / TXT را انتخاب کنید و فرمت‌های خروجی را تیک بزنید — فایل شما بدون استفاده از هوش مصنوعی، مستقیم به فرمت‌های دیگر تبدیل می‌شود.</p><form id="convert-form"><div class="drop" id="convert-drop"><input type="file" id="convert-book" name="convert_book" accept=".epub,.pdf,.srt,.txt,.md"><div><div class="upload-icon">⇄</div><strong>فایل را اینجا رها کنید یا انتخاب کنید</strong><small>EPUB · PDF · SRT · TXT تا ۱ گیگابایت</small></div></div><div class="file-info" id="convert-file-info" style="display:none"></div><div class="grid2"><div style="grid-column:1/-1"><label>فرمت‌های خروجی</label><div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px"><label class="check"><input type="checkbox" name="convert_outputs" value="txt_bilingual">TXT</label><label class="check"><input type="checkbox" name="convert_outputs" value="markdown">Markdown</label><label class="check"><input type="checkbox" name="convert_outputs" value="docx">DOCX</label><label class="check"><input type="checkbox" name="convert_outputs" value="translated_pdf">PDF</label><label class="check"><input type="checkbox" name="convert_outputs" value="json_segments">JSON</label></div><small style="display:block;color:#8892a0;margin-top:6px">حداقل یک فرمت را انتخاب کنید. خروجی‌ها از متن اصلی فایل ساخته می‌شوند.</small></div></div><button class="primary" id="convert-submit" type="submit">تبدیل فایل</button></form><div id="convert-result" style="display:none;margin-top:16px;padding:14px;background:#f4f7ff;border:1px solid #e3e9f2;border-radius:12px"></div></div>'''
CONVERT_SCRIPT = r'''<script>(()=>{const form=document.getElementById('convert-form'),fileInput=document.getElementById('convert-book'),drop=document.getElementById('convert-drop'),info=document.getElementById('convert-file-info'),btn=document.getElementById('convert-submit'),result=document.getElementById('convert-result');if(!form)return;const size=n=>n<1024*1024?(n/1024).toFixed(0)+' KB':(n/1024/1024).toFixed(1)+' MB';function fileChanged(){const f=fileInput.files[0];if(!f){info.style.display='none';return}info.textContent=`${f.name} · ${f.name.split('.').pop().toUpperCase()} · ${size(f.size)}`;info.style.display='block'}fileInput.addEventListener('change',fileChanged);['dragenter','dragover'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',e=>{if(e.dataTransfer.files[0]){fileInput.files=e.dataTransfer.files;fileChanged()}});form.addEventListener('submit',async e=>{e.preventDefault();const f=fileInput.files[0];if(!f){alert('فایل را انتخاب کنید.');return}const checked=[...form.querySelectorAll('input[name="convert_outputs"]:checked')].map(i=>i.value);if(!checked.length){alert('حداقل یک فرمت خروجی انتخاب کنید.');return}btn.disabled=true;btn.textContent='در حال تبدیل…';result.style.display='none';try{const fd=new FormData();fd.append('convert_book',f);checked.forEach(v=>fd.append('convert_outputs',v));const r=await fetch('/api/convert',{method:'POST',body:fd}),d=await r.json();if(!r.ok)throw Error(d.error||'تبدیل ناموفق بود');result.innerHTML=`<strong style="color:var(--green)">تبدیل انجام شد ✓</strong><div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">${d.versions.map(v=>`<a href="${v.download}" style="padding:7px 10px;background:#eaf1ff;color:#2d5ed4;border-radius:8px;font:700 11px Vazirmatn;text-decoration:none">دانلود ${v.name.toUpperCase()}</a>`).join('')}</div>`;result.style.display='block';}catch(err){alert(err.message)}finally{btn.disabled=false;btn.textContent='تبدیل فایل'}}})();</script>'''
PAGE = PAGE.replace('</section><aside class="side">', CONVERT_CARD_HTML + '</section><aside class="side">', 1)
PAGE = PAGE.replace('</body>', CONVERT_SCRIPT + '</body>', 1)
PAGE = install_jobs_dashboard(PAGE)
PAGE = install_workspace(PAGE)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None: return
    def _json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def _job(self, job_id: str) -> Job | None:
        with JOBS_LOCK: return JOBS.get(job_id)
    def _request_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 2 * 1024 * 1024:
            raise ValueError("JSON request is too large.")
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/library/') and parsed.path.endswith('/glossary'):
            query = parse_qs(parsed.query)
            try:
                with JOBS_LOCK:
                    book_jobs = [job for job in JOBS.values() if job.paths]
                for job in book_jobs:
                    _update_progress(job)
                self._json(get_glossary(db, int(parsed.path.split('/')[3]), query.get('from', ['EN'])[0], query.get('to', ['FA'])[0]))
            except LookupError as exc: self._json({'error': str(exc)}, 404)
            except ValueError as exc: self._json({'error': str(exc)}, 400)
            return
        if parsed.path == "/":
            data = inject_language_switcher(welcome_page()).encode("utf-8"); self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        if parsed.path == "/landing":
            lp = Path(__file__).parent.parent / "landing.html"
            alt = Path("D:/J_BookTranslate_V/landing.html")
            src_path = lp if lp.exists() else alt
            if src_path.exists():
                data = src_path.read_bytes(); self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
            self.send_error(404); return
        if parsed.path == "/workspace":
            data = inject_language_switcher(PAGE).encode("utf-8"); self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        if parsed.path == "/account":
            data = account_page().encode("utf-8"); self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        if parsed.path == "/library":
            data = inject_language_switcher(library_page()).encode("utf-8"); self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        if parsed.path == "/api/reader/settings":
            self._json({"value": reading_settings()}); return
        if parsed.path.startswith("/api/reader/") and parsed.path.endswith("/chapters"):
            job = self._job(parsed.path.split("/")[3])
            if not job or job.filetype != "epub" or not job.output_path or not job.output_path.is_file():
                self._json({"error": "Translated EPUB is not available yet."}, 404); return
            try: self._json({"book": job.filename, "items": reader_chapters(job.output_path)})
            except (OSError, ValueError, zipfile.BadZipFile) as exc: self._json({"error": str(exc)}, 422)
            return
        if parsed.path.startswith("/api/reader/") and "/chapters/" in parsed.path:
            pieces = parsed.path.split("/")
            job = self._job(pieces[3])
            if not job or job.filetype != "epub" or not job.output_path or not job.output_path.is_file(): self._json({"error": "Translated EPUB is not available yet."}, 404); return
            try:
                chapter_id = int(pieces[5])
                if len(pieces) > 6 and pieces[6] == "blocks":
                    if not job.paths:
                        self._json({"error": "Original chapter data is not available."}, 404); return
                    self._json({"items": reader_chapter_blocks(job.paths, job.output_path, chapter_id)})
                else:
                    self._json(reader_chapter(job.output_path, chapter_id))
            except (IndexError, ValueError, OSError, zipfile.BadZipFile) as exc: self._json({"error": str(exc)}, 404)
            return
        if parsed.path.startswith("/reader/"):
            job = self._job(parsed.path.rsplit("/", 1)[-1])
            if not job or job.filetype != "epub" or not job.output_path or not job.output_path.is_file(): self.send_error(404); return
            data = reader_page(job.id).encode("utf-8"); self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        if parsed.path == "/api/dashboard/summary":
            self._json(dashboard_summary()); return
        if parsed.path == "/api/account/portal":
            self._json({"overview": account_overview(), "plans": plans_catalog(), "packages": credit_packages(), "api_keys": account_api_keys(), "marketplace": account_marketplace(), "orders": account_orders(), "publisher": publisher_overview()}); return
        if parsed.path == "/api/account/marketplace":
            self._json(account_marketplace(parse_qs(parsed.query).get("kind", [""])[0])); return
        if parsed.path == "/api/jobs":
            status_filter = dict(item.split("=", 1) for item in parsed.query.split("&") if "=" in item).get("status") if parsed.query else None
            with JOBS_LOCK:
                jobs = [_job_payload(job) for job in JOBS.values() if not status_filter or job.status == status_filter]
            self._json({"items": jobs, "total": len(jobs)}); return
        if parsed.path == "/api/languages":
            self._json({"items": [{"code": code, "name": name} for code, name in [("EN", "English"), ("FA", "فارسی"), ("DE", "Deutsch"), ("FR", "Français"), ("AR", "العربية")]]}); return
        if parsed.path == "/api/models":
            self._json({"items": [{"id": model_id, "provider": "configured", "available": True} for model_id in SUPPORTED_MODELS]}); return
        if parsed.path == "/api/profiles":
            self._json({"items": db.fetch_all("SELECT id, name, temperature, preserve_html, preserve_quotes, glossary_id, created_at, updated_at FROM translation_profiles ORDER BY name")}); return
        if parsed.path == "/api/providers":
            config = read_config_safe().get("openai", {})
            self._json({"items": [{"name": "configured", "base_url": config.get("base_url") or DEFAULT_BASE_URL, "enabled": bool(config.get("api_key"))}]}); return
        if parsed.path.startswith("/api/providers/") and parsed.path.endswith("/models"):
            self._json({"items": [{"id": DEFAULT_MODEL, "available": True}]}); return
        if parsed.path == "/api/provider-config":
            # Single source of truth: config/config.yaml. The account
            # settings page and every other API check read from here so
            # the base URL can never drift into a second, disconnected path.
            config = read_config_safe().get("openai", {}) or {}
            translation_config = read_config_safe().get("translation", {}) or {}
            self._json({
                "base_url": config.get("base_url") or DEFAULT_BASE_URL,
                "has_api_key": bool(config.get("api_key")),
                "default_model": translation_config.get("default_model", DEFAULT_MODEL),
                "max_concurrency": max(1, min(int(translation_config.get("max_concurrency", 3)), 12)),
            }); return
        if parsed.path == "/api/glossaries":
            self._json({"items": db.fetch_all("SELECT g.*, COUNT(t.id) AS term_count FROM glossaries g LEFT JOIN glossary_terms t ON t.glossary_id=g.id GROUP BY g.id ORDER BY g.name")}); return
        if parsed.path == "/api/memory/search":
            self._json({"items": db.fetch_all("SELECT * FROM translation_memory ORDER BY last_used_at DESC LIMIT 100")}); return
        if parsed.path == "/api/memory/export":
            self._json({"items": db.fetch_all("SELECT * FROM translation_memory ORDER BY id")}); return
        if parsed.path == "/api/library":
            self._json(library_summary(parsed.query)); return
        if parsed.path.startswith("/api/library/") and parsed.path.endswith("/files"):
            book_id = parsed.path.split("/")[3]
            book = db.fetch_one("SELECT * FROM library_books WHERE id=?", (book_id,))
            if not book: self._json({"error": "Book not found."}, 404); return
            self._json({"book": book, "items": db.fetch_all("SELECT * FROM files WHERE book_id=? ORDER BY id", (book_id,))}); return
        if parsed.path.startswith("/api/library/") and parsed.path.count("/") == 3:
            book_id = parsed.path.rsplit("/", 1)[-1]
            result = next((item for item in library_summary()["items"] if str(item["id"]) == book_id), None)
            if not result: self._json({"error": "Book not found."}, 404); return
            self._json(result); return
        if parsed.path == "/api/analytics/overview":
            self._json(db.fetch_one("SELECT COUNT(*) AS jobs, COALESCE(SUM(progress_completed),0) AS completed_chunks, COALESCE(SUM(input_tokens),0) AS input_tokens, COALESCE(SUM(output_tokens),0) AS output_tokens, COALESCE(SUM(estimated_cost),0) AS estimated_cost, COALESCE(SUM(retry_count),0) AS retries FROM jobs") or {}); return
        if parsed.path == "/api/settings":
            settings = db.fetch_all("SELECT key, value_json, updated_at FROM settings ORDER BY key")
            self._json({"items": [{**item, "value": json.loads(item.pop("value_json"))} for item in settings]}); return
        if parsed.path == "/api/logs":
            level = next((item.split("=", 1)[1] for item in parsed.query.split("&") if item.startswith("level=")), None)
            if level:
                self._json({"items": db.fetch_all("SELECT * FROM job_events WHERE level=? ORDER BY timestamp DESC LIMIT 200", (level.upper(),))})
            else:
                self._json({"items": db.fetch_all("SELECT * FROM job_events ORDER BY timestamp DESC LIMIT 200")})
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/logs"):
            job_id = parsed.path.split("/")[-2]
            self._json({"items": db.fetch_all("SELECT * FROM job_events WHERE job_id=? ORDER BY timestamp ASC", (job_id,))}); return
        if parsed.path == "/api/health":
            try:
                config = get_openai_config()
                if "verify=1" in parsed.query: OpenAI(**config).models.list(); message = "اتصال سرویس ترجمه برقرار است"
                else: message = "تنظیمات سرویس ترجمه آماده است"
                self._json({"status":"ready","message":message}); return
            except Exception as exc: self._json({"status":"error","message":_friendly_error(exc)}); return
        if parsed.path.startswith("/api/jobs/") and parsed.path.count("/") == 3:
            job=self._job(parsed.path.rsplit("/",1)[-1])
            if not job: self._json({"error":"کار موردنظر پیدا نشد."},404); return
            self._json(_job_payload(job)); return
        if parsed.path.startswith("/downloads/"):
            if parsed.path.startswith("/downloads/convert/"):
                rest = parsed.path[len("/downloads/convert/"):]
                if "/" in rest:
                    convert_id, format_name = rest.split("/", 1)
                    entry = CONVERTS.get(convert_id)
                    file_path = (entry or {}).get("generated", {}).get(format_name) if entry else None
                    if not file_path:
                        cand_dir = WEB_OUTPUT_DIR / f"convert_{convert_id}"
                        if cand_dir.is_dir():
                            from app.output.formats import SUFFIXES as _SUFFIXES
                            suffix = _SUFFIXES.get(format_name, "")
                            for cand in cand_dir.glob(f"*{suffix}"):
                                if cand.is_file():
                                    file_path = str(cand)
                                    break
                    p2 = Path(file_path) if file_path else None
                    if not p2 or not p2.is_file() or WEB_OUTPUT_DIR not in p2.parents:
                        self.send_error(404); return
                    self.send_response(200); self.send_header("Content-Type","application/octet-stream"); self.send_header("Content-Disposition",f'attachment; filename="{p2.name}"'); self.send_header("Content-Length",str(p2.stat().st_size)); self.end_headers()
                    with p2.open("rb") as output: shutil.copyfileobj(output,self.wfile)
                    return
            if parsed.path.startswith("/downloads/rescue/"):
                job = self._job(parsed.path.rsplit("/", 1)[-1])
                rescue_path = WEB_OUTPUT_DIR / f"{job.id}_rescue.zip" if job else None
                if not rescue_path or not rescue_path.is_file(): self.send_error(404); return
                self.send_response(200); self.send_header("Content-Type", "application/zip"); self.send_header("Content-Disposition", f'attachment; filename="{rescue_path.name}"'); self.send_header("Content-Length", str(rescue_path.stat().st_size)); self.end_headers()
                with rescue_path.open("rb") as output: shutil.copyfileobj(output, self.wfile)
                return
            if parsed.path.count("/") == 3:
                asset_job_id, asset_name = parsed.path[len("/downloads/"):].split("/", 1)
                asset_job = self._job(asset_job_id)
                asset_path = (asset_job.assets or {}).get(asset_name) if asset_job else None
                asset_file = Path(asset_path) if asset_path else None
                if not asset_file or not asset_file.is_file() or WEB_OUTPUT_DIR not in asset_file.parents:
                    self.send_error(404); return
                self.send_response(200); self.send_header("Content-Type","application/octet-stream"); self.send_header("Content-Disposition",f'attachment; filename="{asset_file.name}"'); self.send_header("Content-Length",str(asset_file.stat().st_size)); self.end_headers()
                with asset_file.open("rb") as output: shutil.copyfileobj(output,self.wfile)
                return
            job=self._job(parsed.path.rsplit("/",1)[-1])
            if not job or not job.output_path or not job.output_path.is_file(): self.send_error(404); return
            self.send_response(200); self.send_header("Content-Type","application/octet-stream"); self.send_header("Content-Disposition",f'attachment; filename="{job.output_path.name}"'); self.send_header("Content-Length",str(job.output_path.stat().st_size)); self.end_headers()
            with job.output_path.open("rb") as output: shutil.copyfileobj(output,self.wfile)
            return
        self.send_error(404)
    def do_POST(self) -> None:
        path=urlparse(self.path).path
        if path.startswith('/api/library/') and path.endswith('/translate'):
            try:
                body = self._request_json()
                book_id = int(path.split('/')[3])
                snapshot = get_glossary(db, book_id, body.get('from_lang', 'EN'), body.get('to_lang', 'FA'))
                auto_extract = body.get('auto_glossary', True)
                if type(auto_extract) is not bool:
                    raise ValueError('گزینهٔ واژه‌نامهٔ خودکار باید روشن یا خاموش باشد.')
                snapshot['auto_extract'] = auto_extract
                source = db.fetch_one("SELECT * FROM files WHERE book_id=? AND kind='original' ORDER BY id LIMIT 1", (book_id,))
                if not source or not Path(source['path']).is_file():
                    raise ValueError('فایل اصلی کتاب در دسترس نیست.')
                model = body.get('model', DEFAULT_MODEL)
                if not isinstance(model, str) or not model.strip() or len(model) > 150 or any(char in model for char in '/\\:'):
                    raise ValueError('مدل نامعتبر است.')
                options = dict(from_lang=snapshot['source_language'], to_lang=snapshot['target_language'], model=model.strip(), mode='fast', prompt='', outputs=body.get('outputs') or '', glossary_snapshot=json.dumps(snapshot, ensure_ascii=False))
                with JOBS_LOCK:
                    if any(item.status in {'queued', 'running'} for item in JOBS.values()):
                        self._json({'error': 'یک ترجمه در حال اجراست.'}, 409); return
                    job = Job(uuid.uuid4().hex[:12], source['display_name'] or Path(source['path']).name, Path(source['path']), source['extension'], source['size_bytes'], options, options['from_lang'], options['to_lang'], options['model'], 'fast')
                    _persist_job(job)
                    db.execute('INSERT INTO files(job_id,book_id,path,kind,display_name,extension,size_bytes,created_at) VALUES (?,?,?,?,?,?,?,?)', (job.id, book_id, source['path'], 'original', job.filename, job.filetype, job.file_size, now()))
                    JOBS[job.id] = job
                threading.Thread(target=_run_job, args=(job,), daemon=True).start()
                self._json({'id': job.id}, 201)
            except LookupError as exc: self._json({'error': str(exc)}, 404)
            except (ValueError, TypeError) as exc: self._json({'error': str(exc)}, 400)
            return
        if path == "/api/convert":
            content_type = self.headers.get("Content-Type","")
            if "multipart/form-data" not in content_type:
                self._json({"error": "فرم آپلود نامعتبر است."},400); return
            try:
                size = int(self.headers.get("Content-Length","0"))
                if not 0 < size <= 1024*1024*1024:
                    raise ValueError("فایل خالی است یا بیش از ۱ گیگابایت حجم دارد.")
                message = BytesParser(policy=policy.default).parsebytes(f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()+self.rfile.read(size))
                fields, upload_name, upload_data = {}, "", b""
                for part in message.iter_parts():
                    name = part.get_param("name",header="content-disposition")
                    if not name: continue
                    payload = part.get_payload(decode=True) or b""
                    if part.get_filename():
                        upload_name, upload_data = part.get_filename(), payload
                    else:
                        value = payload.decode("utf-8",errors="replace")
                        fields[name] = fields[name]+","+value if name in fields else value
            except (ValueError,OSError) as exc:
                self._json({"error":str(exc)},400); return
            filename = _safe_filename(upload_name)
            suffix = Path(filename).suffix.lower()
            if not filename or suffix not in {".epub",".pdf",".srt",".txt",".md"}:
                self._json({"error":"فرمت فایل برای تبدیل پشتیبانی نمی‌شود. (EPUB, PDF, SRT, TXT)"},400); return
            convert_id = uuid.uuid4().hex[:10]
            input_path = UPLOAD_DIR / f"convert_{convert_id}_{filename}"
            try:
                ensure_disk_space(UPLOAD_DIR, required_bytes=len(upload_data) * 3)
                input_path.write_bytes(upload_data)
            except (OSError, ValueError) as exc:
                if input_path.exists(): input_path.unlink(missing_ok=True)
                self._json({"error":str(exc)},400); return
            formats_str = fields.get("convert_outputs") or fields.get("formats") or fields.get("outputs") or ""
            try:
                normalized = normalize_convert_formats(formats_str)
                if not normalized:
                    raise ValueError("حداقل یک فرمت خروجی انتخاب کنید.")
            except ValueError as exc:
                if input_path.exists(): input_path.unlink(missing_ok=True)
                self._json({"error":str(exc)},400); return
            try:
                output_dir = WEB_OUTPUT_DIR / f"convert_{convert_id}"
                output_dir.mkdir(parents=True, exist_ok=True)
                result = convert_file(input_path, output_dir, normalized, title=Path(filename).stem)
                with CONVERTS_LOCK:
                    CONVERTS[convert_id] = {"generated": result["generated"], "source": filename, "created_at": now()}
                versions = [{"name": name, "download": f"/downloads/convert/{convert_id}/{name}", "filename": Path(pp).name} for name, pp in result["generated"].items()]
                self._json({"id": convert_id, "versions": versions, "generated": result["generated"]}, 201)
            except Exception as exc:
                traceback.print_exc()
                self._json({"error": str(exc)}, 500)
            finally:
                try:
                    if input_path.exists(): input_path.unlink()
                except Exception:
                    pass
            return
        # Resource creation and import endpoints
        if path == "/api/glossaries":
            try: body = self._request_json()
            except (ValueError, json.JSONDecodeError) as exc: self._json({"error": str(exc)}, 400); return
            name = str(body.get("name", "")).strip()
            if not name: self._json({"error": "Glossary name is required."}, 400); return
            try:
                gid = db.execute("INSERT INTO glossaries(name, description, created_at, updated_at) VALUES (?, ?, ?, ?)", (name, str(body.get("description", "")), now(), now()))
            except Exception as exc: self._json({"error": "Glossary already exists or is invalid."}, 409); return
            self._json({"id": gid, "name": name}, 201); return
        if path == "/api/memory":
            try: body = self._request_json()
            except (ValueError, json.JSONDecodeError) as exc: self._json({"error": str(exc)}, 400); return
            required = ["source_text", "translated_text", "source_language", "target_language"]
            if any(not str(body.get(k, "")).strip() for k in required): self._json({"error": "source_text, translated_text and languages are required."}, 400); return
            db.execute("INSERT INTO translation_memory(source_text, translated_text, source_language, target_language, source, confidence, last_used_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(source_text, source_language, target_language) DO UPDATE SET translated_text=excluded.translated_text, confidence=excluded.confidence, last_used_at=excluded.last_used_at", tuple(str(body.get(k, "")) for k in required) + (str(body.get("source", "manual")), float(body.get("confidence", 1)), now()))
            self._json({"ok": True}, 201); return
        if path == "/api/memory/import":
            try: body = self._request_json(); entries = body.get("items", body.get("entries", []))
            except (ValueError, json.JSONDecodeError) as exc: self._json({"error": str(exc)}, 400); return
            count = 0
            for item in entries if isinstance(entries, list) else []:
                try:
                    db.execute("INSERT INTO translation_memory(source_text, translated_text, source_language, target_language, source, confidence, last_used_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(source_text, source_language, target_language) DO UPDATE SET translated_text=excluded.translated_text, last_used_at=excluded.last_used_at", (item["source_text"], item["translated_text"], item.get("source_language", "EN"), item.get("target_language", "FA"), item.get("source", "import"), float(item.get("confidence", 1)), now())); count += 1
                except (KeyError, TypeError, ValueError): continue
            self._json({"imported": count}); return
        if path == "/api/profiles":
            try: body = self._request_json()
            except (ValueError, json.JSONDecodeError) as exc: self._json({"error": str(exc)}, 400); return
            name, prompt = str(body.get("name", "")).strip(), str(body.get("system_prompt", "")).strip()
            if not name or not prompt: self._json({"error": "name and system_prompt are required."}, 400); return
            try:
                pid = db.execute("INSERT INTO translation_profiles(name, system_prompt, temperature, preserve_html, preserve_quotes, glossary_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (name, prompt, float(body.get("temperature", .2)), int(bool(body.get("preserve_html", True))), int(bool(body.get("preserve_quotes", True))), body.get("glossary_id"), now(), now()))
            except Exception: self._json({"error": "Profile already exists or is invalid."}, 409); return
            self._json({"id": pid, "name": name}, 201); return
        if path == "/api/jobs/estimate":
            try: body = self._request_json(); size = int(body.get("file_size", 0)); model = body.get("model", DEFAULT_MODEL)
            except (ValueError, json.JSONDecodeError) as exc: self._json({"error": str(exc)}, 400); return
            chunks = max(1, (size + 12000 - 1) // 12000); self._json({"chunks": chunks, "estimated_seconds": chunks * 4, "estimated_cost": 0.0, "model": model}); return
        if path == "/api/provider-config/test":
            try:
                body = self._request_json()
                config, model = _candidate_provider_config(body)
                self._json(_verify_provider_config(config, model)); return
            except Exception as exc:
                self._json({"error": _friendly_error(exc)}, 502); return
        if path == "/api/account/checkout":
            try:
                body = self._request_json(); self._json(start_checkout(str(body.get("kind", "")), str(body.get("reference_id", ""))), 201)
            except LookupError as exc: self._json({"error": str(exc)}, 404)
            except (ValueError, TypeError) as exc: self._json({"error": str(exc)}, 400)
            return
        if path == "/api/account/api-keys":
            try:
                body = self._request_json(); self._json(create_api_key(body.get("name", ""), body.get("scopes", "translate:write jobs:read")), 201)
            except (ValueError, TypeError) as exc: self._json({"error": str(exc)}, 400)
            return
        if path.startswith("/api/account/api-keys/") and path.endswith("/revoke"):
            try: revoke_api_key(int(path.split("/")[-2])); self._json({"ok": True})
            except ValueError as exc: self._json({"error": str(exc)}, 400)
            return
        if path.startswith("/api/account/marketplace/") and path.endswith("/install"):
            try: self._json(install_marketplace_item(path.split("/")[-2]), 201)
            except LookupError as exc: self._json({"error": str(exc)}, 404)
            return
        if path == "/api/account/orders":
            try: self._json(create_order(self._request_json()), 201)
            except (ValueError, TypeError) as exc: self._json({"error": str(exc)}, 400)
            return
        if path == "/api/account/business-requests":
            try: self._json(create_business_request(self._request_json()), 201)
            except (ValueError, TypeError) as exc: self._json({"error": str(exc)}, 400)
            return
        if path.startswith("/api/providers/") and path.endswith("/test"):
            # Legacy path, now backed by the same config.yaml as
            # /api/provider-config/test so results always agree.
            config = read_config_safe().get("openai", {}) or {}
            self._json({"ok": bool(config.get("api_key")), "status": "ready" if config.get("api_key") else "not_configured", "base_url": config.get("base_url") or DEFAULT_BASE_URL}); return
        if path.startswith("/api/glossaries/") and path.endswith("/import"):
            gid = path.split("/")[-2]
            try: body = self._request_json(); terms = body.get("terms", body.get("items", []))
            except (ValueError, json.JSONDecodeError) as exc: self._json({"error": str(exc)}, 400); return
            count = 0
            for term in terms if isinstance(terms, list) else []:
                if not term.get("source_term") or not term.get("target_term"): continue
                db.execute("INSERT INTO glossary_terms(glossary_id, source_term, target_term, notes) VALUES (?, ?, ?, ?) ON CONFLICT(glossary_id, source_term) DO UPDATE SET target_term=excluded.target_term, notes=excluded.notes", (gid, term["source_term"], term["target_term"], term.get("notes", ""))); count += 1
            self._json({"imported": count}); return
        if path.startswith("/api/library/") and path.endswith("/archive"):
            book_id = path.split("/")[-2]
            db.execute("UPDATE library_books SET archived=1, updated_at=? WHERE id=?", (now(), book_id)); db.execute("UPDATE files SET archived=1 WHERE book_id=?", (book_id,)); self._json({"ok": True}); return
        if path.startswith("/api/jobs/") and path.endswith("/stop"):
            job=self._job(path.split("/")[-2])
            if not job or job.status!="running": self._json({"error":"این کار قابل توقف نیست."},400); return
            if job.options.get("mode")=="batch": self._json({"error":"Batch پس از ارسال به سرویس متوقف نمی‌شود."},400); return
            job.stop_event.set(); job.last_activity=job.updated_at=now(); _persist_job(job); _job_event(job, "stop_requested", "درخواست توقف امن ثبت شد."); self._json({"ok":True}); return
        if path.startswith("/api/jobs/") and path.endswith("/cancel"):
            job=self._job(path.split("/")[-2])
            if not job or job.status not in {"queued", "running", "paused"}: self._json({"error":"این کار قابل لغو نیست."},400); return
            job.cancel_requested=True; job.stop_event.set(); job.status="cancelled" if job.status=="queued" else job.status; job.last_activity=job.updated_at=now(); _persist_job(job); self._json({"ok":True}); return
        if path.startswith("/api/jobs/") and path.endswith("/resume"):
            job=self._job(path.split("/")[-2])
            if not job or job.filetype!="epub" or not job.pipeline_job_id or job.status not in {"paused","failed"}: self._json({"error":"این کار قابل ادامه نیست."},400); return
            job.stop_event=threading.Event(); job.cancel_requested=False; job.status="queued"; job.error=None; job.last_activity=job.updated_at=now(); _persist_job(job); _job_event(job, "resume_queued", "ادامه از آخرین جای سالم وارد صف شد."); threading.Thread(target=_run_job,args=(job,),kwargs={"resume":True},daemon=True).start(); self._json({"ok":True},202); return
        if path.startswith("/api/jobs/") and path.endswith("/rescue"):
            job = self._job(path.split("/")[-2])
            if not job: self._json({"error": "Job not found."}, 404); return
            try:
                rescue_path = _rescue_job(job)
                self._json({"ok": True, "download": f"/downloads/rescue/{job.id}", "size": rescue_path.stat().st_size}, 201)
            except OSError as exc: self._json({"error": str(exc)}, 500)
            return
        if path!="/api/jobs": self.send_error(404); return
        content_type=self.headers.get("Content-Type","")
        if "multipart/form-data" not in content_type: self._json({"error":"فرم آپلود نامعتبر است."},400); return
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=1024*1024*1024: raise ValueError("فایل خالی است یا بیش از ۱ گیگابایت حجم دارد.")
            message=BytesParser(policy=policy.default).parsebytes(f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()+self.rfile.read(size)); fields,upload_name,upload_data={},"",b""
            for part in message.iter_parts():
                name=part.get_param("name",header="content-disposition")
                if not name: continue
                payload=part.get_payload(decode=True) or b""
                if part.get_filename(): upload_name,upload_data=part.get_filename(),payload
                else:
                    value=payload.decode("utf-8",errors="replace")
                    fields[name]=fields[name]+","+value if name in fields else value
        except (ValueError,OSError) as exc: self._json({"error":str(exc)},400); return
        filename=_safe_filename(upload_name); suffix=Path(filename).suffix.lower()
        if not filename or suffix not in {".epub",".pdf"}: self._json({"error":"فقط فایل EPUB یا PDF قابل پذیرش است."},400); return
        job_id=uuid.uuid4().hex[:12]; input_path=UPLOAD_DIR/f"{job_id}_{filename}"
        try:
            ensure_disk_space(UPLOAD_DIR, required_bytes=len(upload_data) * 3)
            input_path.write_bytes(upload_data)
            validate_book(input_path)
        except (OSError, ValueError) as exc:
            if input_path.exists(): input_path.unlink()
            self._json({"error":str(exc)},400); return
        options={key:fields.get(key,"").strip() for key in ("from_lang","to_lang","model","mode","prompt","debug")}; options["preserve_voice"] = fields.get("preserve_voice", "false"); options["from_lang"]=options["from_lang"] or "EN"; options["to_lang"]=options["to_lang"] or "FA"; options["model"]=options["model"] or DEFAULT_MODEL; options["mode"]=options["mode"] or "fast"; options["outputs"]=fields.get("outputs",""); options["style_preset"]=fields.get("style_preset","literary")
        job=Job(job_id,filename,input_path,suffix.lstrip("."),len(upload_data),options,options["from_lang"],options["to_lang"],options["model"],options["mode"],style=options.get("style_preset","literary"))
        with JOBS_LOCK: JOBS[job_id]=job
        _persist_job(job)
        _job_event(job, "queued", "کتاب به صف ترجمه اضافه شد.")
        try:
            book_id = _ensure_library_source(job)
            snapshot = get_glossary(db, book_id, options['from_lang'], options['to_lang'])
            snapshot['auto_extract'] = fields.get('auto_glossary', 'false') == 'true' and options['mode'] not in {'batch', 'resumebatch', 'batchcheck', 'test'}
            options['glossary_snapshot'] = json.dumps(snapshot, ensure_ascii=False)
            _persist_job(job)
        except Exception:
            # The translation Job remains authoritative if the library index is unavailable.
            pass
        threading.Thread(target=_run_job,args=(job,),daemon=True).start(); self._json({"id":job_id},201)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if path.startswith('/api/library/') and path.endswith('/glossary'):
            try:
                self._json(save_glossary(db, int(path.split('/')[3]), self._request_json()))
            except LookupError as exc: self._json({'error': str(exc)}, 404)
            except (ValueError, TypeError) as exc: self._json({'error': str(exc)}, 400)
            return
        try: body = self._request_json()
        except (ValueError, json.JSONDecodeError) as exc: self._json({"error": str(exc)}, 400); return
        if path == "/api/account":
            try: self._json(update_account(body))
            except (ValueError, TypeError) as exc: self._json({"error": str(exc)}, 400)
            return
        if path == "/api/provider-config":
            try:
                candidate, default_model = _candidate_provider_config(body)
                verification = _verify_provider_config(candidate, default_model)
                if not verification["model_available"]:
                    self._json({"error": f"مدل {default_model} در Provider انتخاب‌شده پیدا نشد."}, 400); return
                config = read_config_safe()
                config["openai"] = candidate
                translation_config = dict(config.get("translation") or {})
                translation_config["default_model"] = default_model
                max_concurrency = int(body.get("max_concurrency", translation_config.get("max_concurrency", 3)))
                if not 1 <= max_concurrency <= 12:
                    raise ValueError("تعداد درخواست هم‌زمان باید بین 1 تا 12 باشد.")
                translation_config["max_concurrency"] = max_concurrency
                config["translation"] = translation_config
                write_config(config)
                self._json({
                    "base_url": candidate["base_url"],
                    "has_api_key": True,
                    "default_model": default_model,
                    "max_concurrency": max_concurrency,
                    "verified": True,
                    "models": verification["models"],
                }); return
            except ValueError as exc:
                self._json({"error": str(exc)}, 400); return
            except Exception as exc:
                self._json({"error": _friendly_error(exc)}, 502); return
        if path == "/api/reader/settings":
            allowed = set(READING_DEFAULTS)
            clean = {key: value for key, value in body.items() if key in allowed}
            if "reading_font_size" in clean: clean["reading_font_size"] = max(14, min(30, int(clean["reading_font_size"])))
            if "reading_line_height" in clean: clean["reading_line_height"] = max(1.4, min(2.6, float(clean["reading_line_height"])))
            if "reading_width" in clean: clean["reading_width"] = max(560, min(1000, int(clean["reading_width"])))
            if "reading_direction" in clean and clean["reading_direction"] not in {"auto", "rtl", "ltr"}: clean["reading_direction"] = "auto"
            if "reading_theme" in clean and clean["reading_theme"] not in {"light", "night", "sepia"}: clean["reading_theme"] = "light"
            if "reading_mode" in clean and clean["reading_mode"] not in {"translation", "bilingual", "columns", "original"}: clean["reading_mode"] = "translation"
            for key, value in clean.items(): db.execute("INSERT INTO settings(key, value_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at", (key, json.dumps(value, ensure_ascii=False), now()))
            self._json({"ok": True, "value": reading_settings()}); return
        if path == "/api/settings":
            for key, value in body.items(): db.execute("INSERT INTO settings(key, value_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at", (str(key), json.dumps(value, ensure_ascii=False), now()))
            self._json({"ok": True}); return
        if path.startswith("/api/library/") and path.count("/") == 3:
            book_id = path.rsplit("/", 1)[-1]
            title = str(body.get("title", "")).strip()
            if not title: self._json({"error": "Title is required."}, 400); return
            db.execute("UPDATE library_books SET title=?, author=COALESCE(?, author), description=COALESCE(?, description), updated_at=? WHERE id=?", (title, body.get("author"), body.get("description"), now(), book_id)); self._json({"ok": True}); return
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0:2] == ["api", "glossaries"]:
            gid = parts[2]; db.execute("UPDATE glossaries SET name=COALESCE(NULLIF(?, ''), name), description=COALESCE(?, description), updated_at=? WHERE id=?", (str(body.get("name", "")), body.get("description"), now(), gid)); self._json({"ok": True}); return
        if len(parts) == 3 and parts[0:2] == ["api", "profiles"]:
            pid = parts[2]; db.execute("UPDATE translation_profiles SET name=COALESCE(NULLIF(?, ''), name), system_prompt=COALESCE(NULLIF(?, ''), system_prompt), temperature=COALESCE(?, temperature), preserve_html=COALESCE(?, preserve_html), preserve_quotes=COALESCE(?, preserve_quotes), glossary_id=?, updated_at=? WHERE id=?", (str(body.get("name", "")), str(body.get("system_prompt", "")), body.get("temperature"), body.get("preserve_html"), body.get("preserve_quotes"), body.get("glossary_id"), now(), pid)); self._json({"ok": True}); return
        if len(parts) == 3 and parts[0:2] == ["api", "providers"]:
            # Kept for backward compatibility, but writes go through the
            # same config.yaml path as /api/provider-config so this can
            # never diverge into a second base URL.
            provider_id = parts[2]
            db.execute("UPDATE providers SET name=COALESCE(NULLIF(?, ''), name), base_url=COALESCE(NULLIF(?, ''), base_url), default_model=COALESCE(?, default_model), enabled=COALESCE(?, enabled), updated_at=? WHERE id=?", (str(body.get("name", "")), str(body.get("base_url", "")), body.get("default_model"), body.get("enabled"), now(), provider_id))
            if body.get("base_url"): update_openai_config(base_url=str(body.get("base_url")))
            self._json({"ok": True}); return
        self.send_error(404)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0:2] == ["api", "jobs"]:
            job = self._job(parts[2])
            if not job: self._json({"error": "Job not found."}, 404); return
            if job.status in {"queued", "running"}: self._json({"error": "Stop or cancel the job before deleting it."}, 409); return
            with JOBS_LOCK: JOBS.pop(job.id, None)
            meta = JOB_META_DIR / f"{job.id}.json"
            if meta.exists(): meta.unlink()
            db.execute("DELETE FROM jobs WHERE id=?", (job.id,)); self._json({"ok": True}); return
        if len(parts) == 3 and parts[0:2] == ["api", "library"]:
            book_id = parts[2]
            files = db.fetch_all("SELECT path FROM files WHERE book_id=?", (book_id,))
            active = db.fetch_one("SELECT j.id FROM jobs j JOIN files f ON f.job_id=j.id WHERE f.book_id=? AND j.status IN ('queued','running') LIMIT 1", (book_id,))
            if active: self._json({"error": "این کتاب در حال ترجمه است و فعلاً قابل حذف نیست."}, 409); return
            db.execute("DELETE FROM files WHERE book_id=?", (book_id,)); db.execute("DELETE FROM library_books WHERE id=?", (book_id,))
            # Keep deletion scoped to files belonging to this library book.
            for item in files:
                file_path = Path(item["path"])
                if file_path.is_file() and (UPLOAD_DIR in file_path.parents or WEB_OUTPUT_DIR in file_path.parents):
                    try: file_path.unlink()
                    except OSError: pass
            self._json({"ok": True}); return
        table_map = {"glossaries": "glossaries", "memory": "translation_memory", "profiles": "translation_profiles"}
        if len(parts) == 3 and parts[0] == "api" and parts[1] in table_map:
            db.execute(f"DELETE FROM {table_map[parts[1]]} WHERE id=?", (parts[2],)); self._json({"ok": True}); return
        self.send_error(404)


def main() -> None:
    restore_jobs()
    print("J Book Translate UI: http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1",8765),Handler).serve_forever()


if __name__ == "__main__": main()
