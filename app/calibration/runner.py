"""Execute the sealed profile, sharing exact requests with sample generation."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.calibration.documents import digest, write_translation
from app.calibration.engine import compile_request, validate_result
from app.core.config import get_translation_config
from app.core.paths import ensure_temp_structure
from app.jobs.state import _atomic_json
from app.output.formats import generate_outputs
from app.output.segments import build_segments


def run_calibrated_job(service, job, on_started, on_progress):
    session = service.store.get(job.options["calibration_id"])
    sealed = session.get("approved")
    if not sealed or sealed["hash"] != job.options["calibration_hash"] or digest(sealed["artifact"]) != sealed["hash"]:
        raise ValueError("پروفایل تأییدشده با این کار مطابقت ندارد.")
    document = session["document"]
    if hashlib.sha256(Path(document["prepared_path"]).read_bytes()).hexdigest() != sealed["artifact"]["document_hash"]:
        raise ValueError("فایل تأییدشده تغییر کرده است.")
    session["profile"] = sealed["artifact"]["profile"]
    paths = ensure_temp_structure(job.pipeline_job_id or f"calibrated_{job.id}")
    units = document["units"]
    chunks = [(u["id"], u["source"]) for u in units]
    chapter_map = {u["id"]: {"item": u["item"], "pos": u["pos"]} for u in units}
    _atomic_json(paths["chunks_file"], {"chunks": chunks, "chapter_map": chapter_map})
    _atomic_json(Path(paths["job_dir"]) / "profile.json", sealed)
    on_started(Path(paths["job_dir"]).name, paths)
    target = Path(paths["translations_file"])
    translations = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    model = session["profile"]["final_model"]
    by_id = {u["id"]: u for u in units}
    if not set(translations) <= set(by_id):
        raise ValueError("وضعیت ادامه با کتاب تأییدشده یکسان نیست.")
    # Resume identity is pinned to the sealed artifact, not mutable config.yaml.
    state_file = Path(paths["state_file"])
    if state_file.exists():
        old = json.loads(state_file.read_text(encoding="utf-8"))
        if old.get("calibration_hash") != sealed["hash"]:
            raise ValueError("پروفایل نسخهٔ ذخیره‌شده متفاوت است.")

    def commit(unit, result):
        compiled = compile_request(unit, session["profile"], model)
        validate_result(compiled, result)
        translations[unit["id"]] = result["html"]
        _atomic_json(target, translations)
        _atomic_json(state_file, {"calibration_hash": sealed["hash"], "chunks_total": len(units), "chunks_completed": len(translations), "status": "running"})
        on_progress()

    waiting = [u for u in units if u["id"] not in translations]
    workers = max(1, min(12, int(get_translation_config().get("max_concurrency") or 3)))
    # Bounded waves: no unlimited submission; completed paid responses are saved
    # even when a stop arrives or another request in the same wave fails.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for offset in range(0, len(waiting), workers):
            if job.stop_event.is_set():
                return {}
            wave = waiting[offset:offset + workers]
            futures = [(unit, executor.submit(service.translate_unit, session, unit, model, "full")) for unit in wave]
            failure = None
            for unit, future in futures:
                try:
                    result, _ = future.result()
                    commit(unit, result)
                except Exception as exc:
                    failure = failure or exc
            if failure:
                raise failure
    if job.stop_event.is_set():
        return {}
    write_translation(document, translations, job.output_path, session["profile"]["to_lang"])
    segments = build_segments(chunks, translations, chapter_map, "epub")
    manifest = generate_outputs(segments, sealed["artifact"]["outputs"], Path(job.output_path).parent,
                                Path(job.output_path).stem, filetype="epub", title=session["filename"], to_lang=session["profile"]["to_lang"])
    manifest["style"] = session["profile"]["tone"]
    return manifest
