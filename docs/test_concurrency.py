"""Prove the concurrency and the adaptive limiter actually work.

Two claims are checked:

1. With glossary_mode=deferred (the new default) several chunks are genuinely
   in flight at the same time. Before the change, auto_extract forced
   max_workers=1, so every web job ran one chunk at a time.
2. The rate limiter paces, and a 429 shrinks the ceiling and holds everything
   back, while Retry-After wins over the local guess.
"""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.core.rate_limit import AdaptiveRateLimiter
from app.core.paths import ensure_temp_structure
from app.translation import translator
from app.translation.translator import process_translations

failures = 0

# --------------------------------------------------------------------------
print("=== 1. concurrency: are several chunks in flight together? ===")
print("-" * 66)

with tempfile.TemporaryDirectory() as tmp:
    job_id = "conc_test"
    paths = ensure_temp_structure(job_id)
    for key in ("chunks_file", "translations_file", "state_file", "system_prompt_file"):
        Path(paths[key]).unlink(missing_ok=True)
    paths["chunks_file"].write_text(
        json.dumps({"chunks": [], "chapter_map": {}}), encoding="utf-8"
    )
    glossary = Path(paths["job_dir"]) / "glossary.json"
    glossary.write_text(json.dumps({"auto_extract": True, "terms": []}), encoding="utf-8")

    live = {"now": 0}
    lock = threading.Lock()
    peak = {"value": 0, "current": 0}

    def response(content):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        )

    def create(**kwargs):
        system = kwargs["messages"][0]["content"]
        if system.startswith("Extract a concise book glossary"):
            return response(json.dumps({"terms": []}))
        with lock:
            peak["current"] += 1
            peak["value"] = max(peak["value"], peak["current"])
        time.sleep(0.05)
        with lock:
            peak["current"] -= 1
        return response("ok")

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    original_mode = translator._glossary_mode
    original_workers = translator._translation_concurrency
    translator._glossary_mode = lambda: "deferred"
    translator._translation_concurrency = lambda: 4
    try:
        chunks = [(f"c{i}", f"Text {i}") for i in range(8)]
        process_translations(client, chunks, {}, "fast", "EN", "FA", paths)
    finally:
        translator._glossary_mode = original_mode
        translator._translation_concurrency = original_workers

    print(f"  peak chunks in flight: {peak['value']}")
    ok = peak["value"] > 1
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} translation ran concurrently")
    if not ok:
        print("       expected more than one chunk in flight at a time")

# --------------------------------------------------------------------------
print()
print("=== 2. adaptive limiter ===")
print("-" * 66)

limiter = AdaptiveRateLimiter(max_requests_per_minute=60, min_requests_per_minute=4)
print(f"  starts at {limiter.current_rpm} rpm")
ok = limiter.current_rpm == 60
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} initial ceiling")

# 429 should halve the ceiling.
limiter.report_throttled()
print(f"  after one 429: {limiter.current_rpm} rpm")
ok = limiter.current_rpm == 30
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} 429 halves the ceiling")

# Repeated 429s must floor rather than collapse to zero.
for _ in range(10):
    limiter.report_throttled()
print(f"  after many 429s: {limiter.current_rpm} rpm")
ok = limiter.current_rpm >= 4
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} floors instead of collapsing")

# Success should walk it back up to the configured maximum.
for _ in range(100):
    limiter.report_success()
print(f"  after sustained success: {limiter.current_rpm} rpm")
ok = limiter.current_rpm == 60
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} recovers to the configured maximum")

# Retry-After must win over the local cool-off guess.
limiter.reset()
limiter.report_throttled(retry_after=3.0)
remaining = limiter.stats()["cooldown_remaining"]
print(f"  cooldown after Retry-After: 3.0 -> {remaining:.1f}s remaining")
ok = 2.5 <= remaining <= 3.1
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} provider Retry-After is honoured")

# A stop event must interrupt the wait promptly.
stopped = threading.Event()
stopped.set()
started = time.monotonic()
acquired = limiter.acquire(stopped)
elapsed = time.monotonic() - started
print(f"  acquire() with stop set: returned {acquired} in {elapsed * 1000:.0f}ms")
ok = (not acquired) and elapsed < 0.2
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} stop is honoured while waiting")

# Pacing must actually spread requests out.
paced = AdaptiveRateLimiter(max_requests_per_minute=600, min_requests_per_minute=10)
marks = []
for _ in range(4):
    paced.acquire()
    marks.append(time.monotonic())
spread = marks[-1] - marks[0]
print(f"  4 requests at 600 rpm ceiling spread over {spread * 1000:.0f}ms")
ok = spread > 0.05
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} requests are spaced, not burst")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
