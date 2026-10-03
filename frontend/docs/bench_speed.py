"""Measure the wall-clock effect of concurrency, isolated from network noise.

A mock client with realistic per-call latency stands in for the provider, so
the only variable is how many requests are in flight. Two things are measured
per configuration: wall-clock time and total API calls, because speed that
doubles the bill is not a win.

Latency assumptions, roughly typical for a frontier model:
  translation call  4.0 s
  glossary call     2.0 s
"""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.core.paths import ensure_temp_structure
from app.translation import translator
from app.translation.translator import process_translations

TRANSLATE_LATENCY = 4.0
GLOSSARY_LATENCY = 2.0
CHUNKS = 12


def run(glossary_mode, workers, auto_extract=True):
    calls = {"translate": 0, "glossary": 0}
    lock = __import__("threading").Lock()

    def response(content):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    def create(**kwargs):
        system = kwargs["messages"][0]["content"]
        if system.startswith("Extract a concise book glossary"):
            with lock:
                calls["glossary"] += 1
            time.sleep(GLOSSARY_LATENCY)
            return response(json.dumps({"terms": []}))
        with lock:
            calls["translate"] += 1
        time.sleep(TRANSLATE_LATENCY)
        return response("ok")

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    job_id = f"bench_{glossary_mode}_{workers}"
    paths = ensure_temp_structure(job_id)
    try:
        Path(paths["chunks_file"]).write_text(
            json.dumps({"chunks": [], "chapter_map": {}}), encoding="utf-8"
        )
        Path(paths["job_dir"], "glossary.json").write_text(
            json.dumps({"auto_extract": auto_extract, "terms": []}), encoding="utf-8"
        )

        original_mode = translator._glossary_mode
        original_workers = translator._translation_concurrency
        original_build = translator._build_rate_limiter
        translator._glossary_mode = lambda: glossary_mode
        translator._translation_concurrency = lambda: workers
        translator._build_rate_limiter = lambda c: None
        try:
            chunks = [(f"c{i}", f"Text {i}") for i in range(CHUNKS)]
            started = time.monotonic()
            translated, _, _ = process_translations(
                client, chunks, {}, "fast", "EN", "FA", paths
            )
            elapsed = time.monotonic() - started
        finally:
            translator._glossary_mode = original_mode
            translator._translation_concurrency = original_workers
            translator._build_rate_limiter = original_build
    finally:
        shutil.rmtree(Path(paths["job_dir"]), ignore_errors=True)

    assert len(translated) == CHUNKS
    return elapsed, calls["translate"] + calls["glossary"]


def show(label, glossary_mode, workers, auto_extract=True, baseline=None):
    elapsed, api_calls = run(glossary_mode, workers, auto_extract)
    speed = f"{baseline / elapsed:5.2f}x" if baseline else "  --  "
    print(f"{label:44} {elapsed:6.1f}s  {api_calls:4} calls  {speed}")
    return elapsed


print(f"=== {CHUNKS} chunks | translate {TRANSLATE_LATENCY}s | glossary {GLOSSARY_LATENCY}s ===")
print()
print(f"{'configuration':44} {'wall':>7}  {'api':>9}  {'speedup':>7}")
print("-" * 74)

base = show("OLD default (auto_glossary -> sequential)", "inline", 1)
print()
show("NEW default, max_concurrency=3", "deferred", 3, baseline=base)
show("NEW default, max_concurrency=6", "deferred", 6, baseline=base)
show("NEW default, max_concurrency=12", "deferred", 12, baseline=base)
print()
off = show("glossary OFF entirely, 3 workers", "deferred", 3, auto_extract=False, baseline=base)
print()
print(f"  glossary costs {base / off:.1f}x in wall time when left on")
print()
print("Sequential floor is one chunk at a time:")
print(f"  {CHUNKS} x ({TRANSLATE_LATENCY} + {GLOSSARY_LATENCY}) = {CHUNKS * (TRANSLATE_LATENCY + GLOSSARY_LATENCY):.0f}s")
print(f"  {CHUNKS} x {TRANSLATE_LATENCY}                = {CHUNKS * TRANSLATE_LATENCY:.0f}s  (no glossary)")
