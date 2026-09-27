"""Durable, locked and atomic job-state storage."""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.core.paths import ensure_dir, ensure_temp_structure

UTC = timezone.utc
LOCK_TIMEOUT_SECONDS = 30
STALE_LOCK_SECONDS = 300


@contextmanager
def state_lock(paths):
    job_dir = paths.get("job_dir") or Path(paths["translations_file"]).parent
    lock_path = Path(job_dir) / ".state.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    descriptor = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > STALE_LOCK_SECONDS:
                    lock_path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() - started >= LOCK_TIMEOUT_SECONDS:
                raise TimeoutError(f"Timed out waiting for state lock: {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def deduplicate_chunks(chunks):
    seen = set()
    unique = []
    for chunk_id, text in chunks or []:
        key = str(chunk_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append((chunk_id, text))
    return unique


def save_job_state(paths, chunks_total, chunks_completed, translations):
    with state_lock(paths):
        _atomic_json(paths["state_file"], {
            "chunks_total": chunks_total,
            "chunks_completed": chunks_completed,
            "last_updated": datetime.now(UTC).isoformat(),
        })
        _atomic_json(paths["translations_file"], {str(k): v for k, v in translations.items()})


def load_job_state(paths):
    try:
        with state_lock(paths):
            if not paths["chunks_file"].exists():
                return None
            with paths["chunks_file"].open("r", encoding="utf-8") as handle:
                chunks_data = json.load(handle)
            raw_chunks = deduplicate_chunks(chunks_data.get("chunks", []))
            state = {
                "chunks": raw_chunks,
                "chapter_map": {
                    chunk_id: (data["item"], data["pos"])
                    for chunk_id, data in chunks_data.get("chapter_map", {}).items()
                },
                "chunks_total": len(raw_chunks),
                "translations": {},
                "chunks_completed": 0,
            }
            if paths["translations_file"].exists():
                with paths["translations_file"].open("r", encoding="utf-8") as handle:
                    state["translations"] = {str(k): v for k, v in json.load(handle).items()}
                state["chunks_completed"] = len(state["translations"])
            state["last_updated"] = datetime.fromtimestamp(paths["job_dir"].stat().st_mtime, UTC).isoformat()
            return state
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def save_chunks(paths, all_chunks, chapter_map, chunk_contexts=None):
    """Persist the chunk list, the position map, and any per-chunk context.

    ``chunk_contexts`` maps a chunk id to the plain text of the chunks before it.
    It is written alongside the chunks so a resumed job gives the model the same
    context the first run did. Without it a resumed book translates its later
    chunks blind, which is the defect the semantic chunker exists to remove.
    """
    with state_lock(paths):
        chunks = deduplicate_chunks(all_chunks)
        chunk_ids = {str(chunk_id) for chunk_id, _ in chunks}
        clean_map = {chunk_id: value for chunk_id, value in chapter_map.items() if str(chunk_id) in chunk_ids}
        clean_contexts = {
            str(chunk_id): text
            for chunk_id, text in (chunk_contexts or {}).items()
            if str(chunk_id) in chunk_ids and text
        }
        payload = {
            "chunks": [(chunk_id, text) for chunk_id, text in chunks],
            "chapter_map": {chunk_id: {"item": str(item), "pos": pos} for chunk_id, (item, pos) in clean_map.items()},
        }
        if clean_contexts:
            payload["chunk_contexts"] = clean_contexts
        _atomic_json(paths["chunks_file"], payload)


def save_system_prompt(paths, prompt):
    with state_lock(paths):
        path = paths["system_prompt_file"]
        temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(prompt); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp_path, path)


def load_system_prompt(paths):
    path = paths["system_prompt_file"]
    if not path.exists():
        raise FileNotFoundError(f"System prompt file not found: {path}")
    prompt = path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"System prompt is empty: {path}")
    return prompt


def save_translations(paths, translations):
    with state_lock(paths):
        _atomic_json(paths["translations_file"], {str(k): v for k, v in translations.items()})


def find_resumable_jobs(input_epub_path, from_lang, to_lang, model):
    temp_dir = ensure_dir("temp")
    prefix = f"{Path(input_epub_path).stem}_{from_lang}_{to_lang}_{model}_"
    jobs = []
    if not temp_dir.exists():
        return jobs
    for job_dir in temp_dir.iterdir():
        if not job_dir.is_dir() or not job_dir.name.startswith(prefix):
            continue
        try:
            paths = ensure_temp_structure(job_dir.name)
            state = load_job_state(paths)
            if not state:
                continue
            timestamp = job_dir.name.rsplit("_", 2)[-2:]
            raw_timestamp = "_".join(timestamp)
            jobs.append((job_dir.name, raw_timestamp, {
                "chunks_total": state["chunks_total"],
                "chunks_completed": state["chunks_completed"],
                "last_updated": state["last_updated"],
            }))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return sorted(jobs, key=lambda item: item[2]["last_updated"], reverse=True)
