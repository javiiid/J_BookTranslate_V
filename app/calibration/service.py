"""Sample selection, tone tuning, approvals, estimates and guarded execution."""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
import uuid
from pathlib import Path

from app.calibration.documents import digest, prepare
from app.calibration.engine import (TONES, VERSION, GLOSSARY_SYSTEM, compile_request,
    cost_micros, parse_json, token_estimate, token_reservation, validate_result)
from app.calibration.store import Store, Conflict, BudgetExceeded, now
from app.core.config import get_openai_config, read_config_safe
from app.core.models import is_supported_model, resolve_default_model
from app.glossary.proposal import key as term_key
from app.glossary.service import language, matching_terms
from app.jobs.estimate import PRICING
from app.output.formats import normalize_outputs


def integer(value, minimum, maximum, name):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"مقدار «{name}» نامعتبر است.")
    return value


def provider_identity():
    cfg = get_openai_config()
    return digest({"url": cfg["base_url"], "credential": hashlib.sha256(cfg["api_key"].encode()).hexdigest()})


def validate_fallback_model(fallback_model, final_model):
    """Validate an optional cheaper fallback model against the final model.

    Returns the cleaned model name or None when no fallback was given.
    """
    if fallback_model is None or (isinstance(fallback_model, str) and not fallback_model.strip()):
        return None
    if not isinstance(fallback_model, str) or not is_supported_model(fallback_model.strip()):
        raise ValueError("مدل جایگزین پشتیبانی نمی‌شود.")
    fallback_model = fallback_model.strip()
    if fallback_model == final_model:
        raise ValueError("مدل جایگزین باید با مدل نهایی متفاوت باشد.")
    from app.jobs.estimate import PRICING
    fallback_price = PRICING.get(fallback_model)
    final_price = PRICING.get(final_model)
    if fallback_price is None or final_price is None:
        raise ValueError("قیمت مدل‌ها برای مقایسه مشخص نیست؛ مدل جایگزین پذیرفته نشد.")
    if fallback_price[0] >= final_price[0]:
        raise ValueError("مدل جایگزین باید ارزان‌تر از مدل نهایی باشد.")
    return fallback_model


class CalibrationService:
    def __init__(self, database, root, client_factory=None):
        self.store = Store(database)
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.client_factory = client_factory or self._client
        self.lock = threading.RLock()
        self.execution_lock = threading.RLock()

    @staticmethod
    def _client():
        from openai import OpenAI
        return OpenAI(**get_openai_config(), max_retries=0, timeout=90)

    def recover(self):
        # Never automatically retry an operation that may have reached a provider.
        for session in self.store.list():
            if session.get("busy"):
                try:
                    op = self.store.operation(session["busy"])
                    op.update(status="failed", error="اجرای قبلی با توقف سرور قطع شد. هزینهٔ نامشخص رزرو می‌ماند؛ وضعیت را بررسی کنید.")
                    self.store.update_operation(op)
                except LookupError:
                    pass
                self.store.change(session["id"], lambda s: s.update(busy=None))
        self.store.database.execute("UPDATE calibration_attempts SET status='uncertain' WHERE status='dispatching'")

    def create(self, source, filename, body):
        source = Path(source)
        model = body.get("model") or resolve_default_model()
        final_model = body.get("final_model") or model
        if not is_supported_model(model) or not is_supported_model(final_model):
            raise ValueError("مدل انتخاب‌شده پشتیبانی نمی‌شود.")
        fallback_model = validate_fallback_model(body.get("fallback_model"), final_model)
        tone = body.get("tone", "literary")
        if tone not in TONES:
            raise ValueError("لحن نامعتبر است.")
        outputs = normalize_outputs(body.get("outputs") or [])
        if set(outputs) & {"srt", "quality_report"}:
            raise ValueError("زیرنویس و ارزیابی مدل جداگانه در جریان نمونه پشتیبانی نمی‌شود؛ قالب خروجی دیگری انتخاب کنید.")
        profile = {"tone": tone, "from_lang": language(body.get("from_lang", "EN")), "to_lang": language(body.get("to_lang", "FA")),
                   "model": model, "final_model": final_model, "fallback_model": fallback_model, "glossary": [], "instructions": "", "provider": provider_identity(), "version": VERSION}
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        # Reopening the same book/configuration keeps drafts, approvals and spending.
        for existing in self.store.list():
            if (existing["document"]["source_hash"] == source_hash and existing["outputs"] == outputs
                and all(existing["profile"].get(k) == profile[k] for k in ("from_lang", "to_lang", "model", "final_model", "fallback_model", "provider"))):
                return self.payload(existing)
        identifier = uuid.uuid4().hex
        document = prepare(source, self.root / identifier, profile["from_lang"])
        timestamp = now()
        session = {"id": identifier, "revision": 0, "state": "AWAITING_USER_CALIBRATION", "filename": filename,
                   "profile": profile, "document": document, "selected": document.pop("selected"), "results": {},
                   "approvals": {}, "approved": None, "busy": None, "job_id": None, "outputs": outputs,
                   "created_at": timestamp, "updated_at": timestamp, "generation_counts": {},
                   "budget_id": digest([source_hash, profile["from_lang"], profile["to_lang"]]),
                   "budget": {"sample_tokens": 150000, "total_tokens": 3000000, "max_calls": 18, "max_cost_micros": None}}
        self.store.create(session)
        return self.payload(session)

    def rates(self, model):
        configured = (read_config_safe().get("calibration") or {}).get("rates", {}).get(model)
        if isinstance(configured, dict):
            values = [configured.get("input_per_million"), configured.get("output_per_million")]
            try:
                if all(v is not None and math.isfinite(float(v)) and float(v) >= 0 for v in values):
                    return tuple(float(v) for v in values), "configured"
            except (ValueError, TypeError):
                pass
        return PRICING.get(model), "estimated" if model in PRICING else "unknown"

    def quote(self, session):
        profile = session["profile"]
        model = profile["final_model"]
        rate, provenance = self.rates(model)
        total_input, total_output, reusable, sample_cost, remaining_cost = 0, 0, 0, 0, 0
        for unit in session["document"]["units"]:
            compiled = compile_request(unit, profile, model)
            if not compiled["slots"]:
                continue
            incoming = token_estimate(compiled["request"])
            outgoing = min(4096, max(100, int(len(unit["plain"]) * 0.65)))
            cost = cost_micros(incoming, outgoing, rate)
            total_input += incoming
            total_output += outgoing
            if self.current_result(session, unit, model):
                reusable += 1
            else:
                remaining_cost += cost or 0
                if unit["id"] in session["selected"]:
                    sample_cost += cost or 0
        b = self.store.budget(session["budget_id"])
        plan = digest([profile, session["document"]["prepared_hash"], session["selected"], session["outputs"], session["approvals"]])
        quote_id = digest([plan, rate, provenance, reusable, b["sample_spent"], b["full_spent"]])
        return {"id": quote_id, "plan_hash": plan, "pricing": provenance, "rate": rate,
                "input_tokens": total_input, "output_tokens": total_output, "reusable_units": reusable,
                "remaining_cost_low": round(remaining_cost / 1e6 * .8, 6) if rate else None,
                "remaining_cost_high": round(remaining_cost / 1e6 * 1.35, 6) if rate else None,
                "sample_cost": sample_cost / 1e6 if rate else None,
                "spent_cost": b["cost_spent"] / 1e6, "reserved_cost": b["cost_reserved"] / 1e6,
                "spent_tokens": b["sample_spent"] + b["full_spent"],
                "sample_spent_tokens": b["sample_spent"], "reserved_tokens": b["sample_reserved"] + b["full_reserved"],
                "sample_calls": b["sample_calls"], "token_method": "conservative_estimate"}

    def current_result(self, session, unit, model=None):
        compiled = compile_request(unit, session["profile"], model or session["profile"]["final_model"])
        return session["results"].get(compiled["key"])

    def payload(self, session):
        samples = []
        for identifier in session["selected"]:
            unit = next(u for u in session["document"]["units"] if u["id"] == identifier)
            compiled = compile_request(unit, session["profile"], session["profile"]["final_model"])
            result = session["results"].get(compiled["key"])
            final_verified = bool(result)
            if result is None:
                draft = compile_request(unit, session["profile"], session["profile"]["model"])
                result = session["results"].get(draft["key"])
            samples.append({"id": identifier, "chapter": unit["chapter"], "role": unit["role"],
                            "source": unit["plain"], "slots": compiled["slots"], "result": result,
                            "final_verified": final_verified,
                            "approved": bool(result and session["approvals"].get(identifier) == digest([compiled["key"], result]))})
        profile = {k: v for k, v in session["profile"].items() if k != "provider"}
        return {"id": session["id"], "revision": session["revision"], "state": session["state"],
                "filename": session["filename"], "profile": profile, "samples": samples,
                "candidates": [{"id": u["id"], "chapter": u["chapter"], "role": u["role"], "excerpt": u["plain"][:130]} for u in session["document"]["units"] if u["plain"]],
                "unit_count": len(session["document"]["units"]), "warnings": session["document"]["warnings"],
                "budget": session["budget"], "quote": self.quote(session), "busy": session["busy"],
                "job_id": session["job_id"], "approved_profile_hash": (session.get("approved") or {}).get("hash"),
                "tones": [{"id": k, "label": v["label"], "description": v["description"]} for k, v in TONES.items()]}

    def edit(self, identifier, body):
        def change(s):
            self.editable(s)
            p = s["profile"]
            if "tone" in body:
                if body["tone"] not in TONES:
                    raise ValueError("لحن نامعتبر است.")
                p["tone"] = body["tone"]
            for field in ("model", "final_model"):
                if field in body:
                    if not is_supported_model(body[field]):
                        raise ValueError("مدل نامعتبر است.")
                    p[field] = body[field]
            if "fallback_model" in body:
                p["fallback_model"] = validate_fallback_model(body["fallback_model"], p["final_model"])
            elif p.get("fallback_model"):
                # final_model may have changed above; the old fallback must
                # still be cheaper than the new final model.
                p["fallback_model"] = validate_fallback_model(p["fallback_model"], p["final_model"])
            if "instructions" in body:
                if not isinstance(body["instructions"], str) or len(body["instructions"]) > 2000:
                    raise ValueError("راهنمای لحن حداکثر ۲۰۰۰ نویسه است.")
                p["instructions"] = body["instructions"].strip()
            if "selected" in body:
                ids = body["selected"]
                valid = {u["id"] for u in s["document"]["units"] if u["plain"]}
                if not isinstance(ids, list) or not 1 <= len(ids) <= 3 or len(set(ids)) != len(ids) or not set(ids) <= valid:
                    raise ValueError("یک تا سه نمونهٔ متفاوت انتخاب کنید.")
                s["selected"] = ids
            if "glossary" in body:
                p["glossary"] = self.clean_terms(body["glossary"], p["glossary"], body.get("unlock_ids", []))
            if "budget" in body:
                b = body["budget"]
                s["budget"] = {"sample_tokens": integer(b.get("sample_tokens"), 1000, 5000000, "توکن نمونه"),
                               "total_tokens": integer(b.get("total_tokens"), 1000, 100000000, "توکن کل"),
                               "max_calls": integer(b.get("max_calls"), 1, 100, "درخواست نمونه"),
                               "max_cost_micros": None if b.get("max_cost_micros") is None else integer(b["max_cost_micros"], 1, 1000000000, "سقف دلار")}
                if s["budget"]["sample_tokens"] > s["budget"]["total_tokens"]:
                    raise ValueError("سقف نمونه از سقف کل بزرگ‌تر است.")
                if s["budget"]["max_cost_micros"] is not None and any(self.rates(p[m])[1] != "configured" for m in ("model", "final_model")):
                    raise ValueError("برای سقف دلاری ابتدا نرخ واقعی مدل‌ها را در calibration.rates ثبت کنید.")
            s.update(revision=s["revision"] + 1, state="AWAITING_USER_CALIBRATION", approved=None)
        return self.payload(self.store.change(identifier, change, body.get("revision", -1)))

    @staticmethod
    def editable(session):
        if session.get("busy"):
            raise Conflict("عملیات قبلی هنوز در حال اجراست.")
        if session.get("job_id"):
            raise Conflict("این پروفایل وارد ترجمهٔ کامل شده و تغییرناپذیر است.")

    @staticmethod
    def clean_terms(terms, previous, unlock_ids):
        if not isinstance(terms, list) or len(terms) > 500:
            raise ValueError("حداکثر ۵۰۰ اصطلاح مجاز است.")
        cleaned, seen = [], set()
        for t in terms:
            if not isinstance(t, dict):
                raise ValueError("اصطلاح نامعتبر است.")
            item = {"id": str(t.get("id") or uuid.uuid4().hex), "source_term": str(t.get("source_term", "")).strip(),
                    "target_term": str(t.get("target_term", "")).strip(), "notes": str(t.get("notes", "")),
                    "kind": str(t.get("kind", "term")), "approved": t.get("approved") is True, "locked": t.get("locked") is True,
                    "evidence_id": str(t.get("evidence_id", ""))}
            key = term_key(item["source_term"])
            if not key or not item["target_term"] or key in seen or len(item["source_term"]) > 200 or len(item["target_term"]) > 200 or len(item["notes"]) > 1000:
                raise ValueError("اصطلاح خالی، تکراری یا بیش از حد طولانی است.")
            if item["locked"] and not item["approved"]:
                raise ValueError("فقط اصطلاح تأییدشده قابل قفل است.")
            seen.add(key)
            cleaned.append(item)
        for old in previous:
            if old.get("locked") and old["id"] not in unlock_ids:
                new = next((t for t in cleaned if t["id"] == old["id"]), None)
                if new != old:
                    raise Conflict("برای تغییر اصطلاح قفل‌شده ابتدا قفل آن را باز کنید.")
        return cleaned

    def call(self, session, request, phase):
        if self.client_factory == self._client and session["profile"]["provider"] != provider_identity():
            raise Conflict("ارائه‌دهنده تغییر کرده است؛ کتاب را با تنظیمات جدید باز کنید.")
        reserved = token_reservation(request)
        rate, provenance = self.rates(request["model"])
        # Unknown/indicative rates are allowed under an explicitly shown token cap.
        if session["budget"].get("max_cost_micros") is not None and provenance != "configured":
            raise BudgetExceeded("قیمت تأییدشده برای سقف دلاری موجود نیست.")
        reservation_cost = cost_micros(reserved - request["max_tokens"], request["max_tokens"], rate)
        attempt = self.store.reserve(session, reserved, reservation_cost, phase)
        try:
            response = self.client_factory().chat.completions.create(**request)
        except BaseException:
            self.store.uncertain(attempt)
            raise
        usage = getattr(response, "usage", None)
        incoming = getattr(usage, "prompt_tokens", None)
        outgoing = getattr(usage, "completion_tokens", None)
        if type(incoming) is int and incoming >= 0 and type(outgoing) is int and outgoing >= 0:
            tokens = incoming + outgoing
            cost = cost_micros(incoming, outgoing, rate)
        else:
            tokens, cost = reserved, reservation_cost
        self.store.settle(attempt, tokens, cost, {"input": incoming, "output": outgoing, "measured": incoming is not None, "provider_request": getattr(response, "id", None)})
        if not response.choices or response.choices[0].finish_reason not in (None, "stop"):
            raise ValueError("پاسخ مدل کامل نشد؛ نمونه را کوتاه‌تر کنید یا دوباره تلاش کنید.")
        return parse_json(response.choices[0].message.content)

    def translate_unit(self, session, unit, model, phase="sample"):
        compiled = compile_request(unit, session["profile"], model)
        local = session["results"].get(compiled["key"])
        if local:
            validate_result(compiled, local)
            return local, compiled["key"]
        cached = self.store.cached(compiled["key"])
        if cached:
            validate_result(compiled, cached)
            return {**cached, "reused": True}, compiled["key"]
        if not compiled["slots"]:
            return {"translations": [], "html": unit["source"], "plain": "", "model": model, "origin": "protected", "reused": True}, compiled["key"]
        result = validate_result(compiled, self.call(session, compiled["request"], phase))
        result.update(model=model, origin="model", reused=False, created_at=now())
        self.store.cache(compiled["key"], result)
        return result, compiled["key"]

    def enqueue(self, identifier, action, body, request_key):
        if action not in {"generate", "propose"}:
            raise ValueError("عملیات نامعتبر است.")
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 200:
            raise ValueError("شناسهٔ درخواست لازم است.")
        operation = {"id": uuid.uuid4().hex, "session_id": identifier, "action": action, "status": "queued", "completed": 0, "total": 0, "error": None}
        with self.lock:
            operation, fresh = self.store.save_operation(operation, request_key, digest([action, body]))
            if not fresh:
                return operation
            try:
                def claim(s):
                    self.editable(s)
                    s["busy"] = operation["id"]
                session = self.store.change(identifier, claim, body.get("revision", -1))
            except Exception as exc:
                operation.update(status="failed", error=str(exc))
                self.store.update_operation(operation)
                raise
        threading.Thread(target=self._operation, args=(operation, session, body), daemon=True).start()
        return operation

    def _operation(self, operation, session, body):
        try:
            operation["status"] = "running"
            self.store.update_operation(operation)
            with self.execution_lock:
                if operation["action"] == "propose":
                    self._propose(session)
                else:
                    selected = body.get("sample_ids") or session["selected"]
                    if not isinstance(selected, list) or not set(selected) <= set(session["selected"]):
                        raise ValueError("نمونهٔ نامعتبر است.")
                    units = [u for u in session["document"]["units"] if u["id"] in selected]
                    model = session["profile"]["final_model" if body.get("final", True) else "model"]
                    operation["total"] = len(units)
                    for unit in units:
                        if self.store.operation(operation["id"]).get("cancel_requested"):
                            operation["status"] = "cancelled"
                            break
                        result, key = self.translate_unit(session, unit, model)
                        self.store.change(session["id"], lambda s, k=key, r=result: s["results"].update({k: r}))
                        operation["completed"] += 1
                        self.store.update_operation(operation)
            if operation["status"] != "cancelled":
                operation["status"] = "succeeded"
        except Exception as exc:
            operation.update(status="failed", error=str(exc)[:1000])
        finally:
            self.store.update_operation(operation)
            self.store.change(session["id"], lambda s: s.update(busy=None, revision=s["revision"] + 1))

    def _propose(self, session):
        units = [u for u in session["document"]["units"] if u["plain"]]
        picked = sorted(set(round(i * (len(units) - 1) / max(1, min(12, len(units)) - 1)) for i in range(min(12, len(units)))))
        evidence = [{"id": units[i]["id"], "text": units[i]["plain"][:1600]} for i in picked]
        request = {"model": session["profile"]["model"], "messages": [{"role": "system", "content": GLOSSARY_SYSTEM}, {"role": "user", "content": json.dumps({"target_language": session["profile"]["to_lang"], "evidence": evidence, "locked": [t for t in session["profile"]["glossary"] if t["locked"]]}, ensure_ascii=False)}], "temperature": 0.0, "max_tokens": 4096}
        response = self.call(session, request, "sample")
        existing = session["profile"]["glossary"]
        seen = {term_key(t["source_term"]) for t in existing}
        proposals = []
        for term in response.get("terms", [])[:40]:
            if not isinstance(term, dict) or not isinstance(term.get("source_term"), str):
                continue
            witness = next((e for e in evidence if e["id"] == term.get("evidence_id")), None)
            if not witness or not matching_terms(witness["text"], {"terms": [term]}) or term_key(term["source_term"]) in seen:
                continue
            term.update(id=uuid.uuid4().hex, approved=False, locked=False)
            proposals.append(term)
            seen.add(term_key(term["source_term"]))
        clean = self.clean_terms(existing + proposals, existing, [])
        self.store.change(session["id"], lambda s: (s["profile"].update(glossary=clean), s.update(approved=None, state="AWAITING_USER_CALIBRATION")))

    def feedback(self, identifier, body):
        def apply(s):
            self.editable(s)
            unit = next((u for u in s["document"]["units"] if u["id"] == body.get("sample_id") and u["id"] in s["selected"]), None)
            if not unit:
                raise ValueError("نمونه پیدا نشد.")
            compiled = compile_request(unit, s["profile"], s["profile"]["final_model"])
            if compiled["key"] not in s["results"]:
                raise Conflict("ابتدا نمونه را با مدل نهایی تولید کنید.")
            result = validate_result(compiled, {"translations": body.get("translations")})
            result.update(model=s["profile"]["final_model"], origin="human_edit", reused=False, created_at=now())
            s["results"][compiled["key"]] = result
            s.update(revision=s["revision"] + 1, approved=None, state="AWAITING_USER_CALIBRATION")
        return self.payload(self.store.change(identifier, apply, body.get("revision", -1)))

    def approve_sample(self, identifier, body):
        def apply(s):
            self.editable(s)
            unit = next((u for u in s["document"]["units"] if u["id"] == body.get("sample_id") and u["id"] in s["selected"]), None)
            if not unit:
                raise ValueError("نمونه پیدا نشد.")
            compiled = compile_request(unit, s["profile"], s["profile"]["final_model"])
            result = s["results"].get(compiled["key"])
            if not result:
                raise Conflict("نمونه با تنظیمات و مدل نهایی تولید نشده است.")
            validate_result(compiled, result)
            s["approvals"][unit["id"]] = digest([compiled["key"], result])
            s["revision"] += 1
        return self.payload(self.store.change(identifier, apply, body.get("revision", -1)))

    def approve(self, identifier, body):
        def apply(s):
            self.editable(s)
            for unit in [u for u in s["document"]["units"] if u["id"] in s["selected"]]:
                compiled = compile_request(unit, s["profile"], s["profile"]["final_model"])
                result = s["results"].get(compiled["key"])
                if not result or s["approvals"].get(unit["id"]) != digest([compiled["key"], result]):
                    raise Conflict("همهٔ نمونه‌های فعلی باید با مدل نهایی بررسی و تأیید شوند.")
                validate_result(compiled, result)
            artifact = {"profile": s["profile"], "document_hash": s["document"]["prepared_hash"], "approvals": s["approvals"], "outputs": s["outputs"]}
            s["approved"] = {"hash": digest(artifact), "artifact": json.loads(json.dumps(artifact)), "approved_at": now()}
            s.update(state="CALIBRATED_AND_ESTIMATED", revision=s["revision"] + 1)
        return self.payload(self.store.change(identifier, apply, body.get("revision", -1)))

    def claim_start(self, identifier, body):
        def apply(s):
            if s.get("job_id"):
                return  # Repeated start returns the same durable job ID.
            self.editable(s)
            if not s.get("approved") or s["state"] != "CALIBRATED_AND_ESTIMATED":
                raise Conflict("ابتدا نمونه‌ها و پروفایل را تأیید کنید.")
            if body.get("quote_id") != self.quote(s)["id"]:
                raise Conflict("برآورد هزینه تغییر کرده است؛ برآورد تازه را بررسی کنید.")
            if hashlib.sha256(Path(s["document"]["prepared_path"]).read_bytes()).hexdigest() != s["document"]["prepared_hash"]:
                raise Conflict("فایل کتاب پس از تأیید تغییر کرده است.")
            s.update(job_id=uuid.uuid4().hex[:12], state="FULL_PROCESSING", revision=s["revision"] + 1)
        with self.lock:
            current = self.store.get(identifier)
            return self.store.change(identifier, apply, None if current.get("job_id") else body.get("revision", -1))
