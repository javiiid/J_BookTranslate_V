"""Small HTTP adapter; business rules live in CalibrationService."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.parse import urlparse

from app.calibration.service import CalibrationService
from app.calibration.store import Conflict, BudgetExceeded

_service = None
_lock = threading.Lock()


def get_service():
    global _service
    with _lock:
        if _service is None:
            from app.storage.database import db
            from app.core.paths import ensure_dir
            _service = CalibrationService(db, ensure_dir("data") / "calibrations")
            _service.recover()
    return _service


def start_job(service, session):
    from app import web
    identifier = session["job_id"]
    with web.JOBS_LOCK:
        if identifier in web.JOBS:
            return {"id": identifier}
        p = session["approved"]["artifact"]["profile"]
        path = Path(session["document"]["prepared_path"])
        options = {"from_lang": p["from_lang"], "to_lang": p["to_lang"], "model": p["final_model"], "mode": "fast", "prompt": "",
                   "style_preset": p["tone"], "calibration_id": session["id"], "calibration_hash": session["approved"]["hash"],
                   "glossary_snapshot": json.dumps({"terms": [t for t in p["glossary"] if t["approved"]], "auto_extract": False}, ensure_ascii=False)}
        job = web.Job(identifier, Path(session["filename"]).stem + ".epub", path, "epub", path.stat().st_size,
                      options, p["from_lang"], p["to_lang"], p["final_model"], "fast", style=p["tone"])
        web.JOBS[identifier] = job
        web._persist_job(job)
        web._ensure_library_source(job)
        web._job_event(job, "queued", "نمونه‌ها تأیید شد؛ ترجمه با پروفایل قفل‌شده وارد صف شد.")
        threading.Thread(target=web._run_job, args=(job,), daemon=True).start()
    return {"id": identifier}


def handle(handler, method):
    path = urlparse(handler.path).path
    if not (path == "/api/calibrations" or path.startswith("/api/calibrations/") or path.startswith("/api/calibration-operations/")):
        return False
    try:
        service = get_service()
        if path.startswith("/api/calibration-operations/"):
            bits = path.split("/")
            operation = service.store.operation(bits[3])
            if method == "POST" and len(bits) == 5 and bits[4] == "cancel":
                operation["cancel_requested"] = True
                service.store.update_operation(operation)
            elif method != "GET":
                raise LookupError("مسیر پیدا نشد.")
            handler._json(operation)
            return True
        if path == "/api/calibrations":
            if method == "GET":
                handler._json({"items": [{"id": s["id"], "filename": s["filename"], "state": s["state"], "updated_at": s["updated_at"]} for s in service.store.list()]})
                return True
            if method != "POST":
                raise LookupError("مسیر پیدا نشد.")
            from app import web
            body = handler._request_json()
            token = body.get("upload_id", "")
            if not isinstance(token, str) or not token or Path(token).name != token or '/' in token or '\\' in token:
                raise ValueError("شناسهٔ فایل نامعتبر است.")
            source = (web.UPLOAD_DIR / token).resolve()
            if not source.is_relative_to(web.UPLOAD_DIR.resolve()) or not source.is_file():
                raise LookupError("فایل بارگذاری‌شده پیدا نشد.")
            handler._json(service.create(source, token.split('_', 1)[-1], body), 201)
            return True
        bits = path.split("/")
        identifier = bits[3]
        if method == "GET" and len(bits) == 4:
            handler._json(service.payload(service.store.get(identifier)))
            return True
        body = handler._request_json()
        action = bits[4] if len(bits) == 5 else ""
        if method == "PUT" and not action:
            result = service.edit(identifier, body)
        elif method == "POST" and action in {"generate", "propose"}:
            result = service.enqueue(identifier, action, body, handler.headers.get("Idempotency-Key", ""))
            handler._json(result, 202)
            return True
        elif method == "POST" and action == "feedback":
            result = service.feedback(identifier, body)
        elif method == "POST" and action == "approve-sample":
            result = service.approve_sample(identifier, body)
        elif method == "POST" and action == "approve":
            result = service.approve(identifier, body)
        elif method == "POST" and action == "start":
            result = start_job(service, service.claim_start(identifier, body))
        else:
            raise LookupError("مسیر پیدا نشد.")
        handler._json(result)
    except Conflict as exc:
        handler._json({"error": str(exc), "code": "CALIBRATION_CONFLICT"}, 409)
    except BudgetExceeded as exc:
        handler._json({"error": str(exc), "code": "BUDGET_EXCEEDED"}, 422)
    except LookupError as exc:
        handler._json({"error": str(exc)}, 404)
    except (ValueError, TypeError, KeyError) as exc:
        handler._json({"error": str(exc)}, 422)
    except Exception:
        handler._json({"error": "آماده‌سازی نمونه ناموفق بود؛ فایل و تنظیمات اتصال را بررسی کنید."}, 500)
    return True
