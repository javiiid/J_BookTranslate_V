"""Capture a live inventory of the Python API, for the port.

Phase 0 captured the "before" UI. This re-captures the *contract* against the
running backend, because the port adds types for every screen and a guessed
shape produces a component that renders an empty state forever.

Two things are recorded per endpoint: the real response shape, and any endpoint
the front end needs that does not exist. The second half matters as much as the
first -- a missing endpoint is a decision to make, not something to discover
later as an empty table.
"""
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8765"
OUT = Path(r"D:\J_BookTranslate_V\frontend\docs\inventory\phase3")
OUT.mkdir(parents=True, exist_ok=True)


def get(path):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"null")
        except json.JSONDecodeError:
            return exc.code, {"__text": raw[:200].decode("utf-8", "replace")}
    except Exception as exc:  # noqa: BLE001
        return 0, {"__error": f"{type(exc).__name__}: {exc}"}


def shape(value, depth=0):
    """Describe a response as a TS-ish shape, not the whole payload."""
    if depth > 3:
        return "..."
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            out[key] = shape(item, depth + 1)
        return out
    if isinstance(value, list):
        if not value:
            return []
        return [shape(value[0], depth + 1), f"<{len(value)} items>"]
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return f"string ({len(value)} chars)" if len(value) > 60 else "string"
    return type(value).__name__


for _ in range(30):
    try:
        urllib.request.urlopen(f"{BASE}/api/health", timeout=1)
        break
    except Exception:  # noqa: BLE001
        time.sleep(0.5)

# --- read-only endpoints, safe to call -----------------------------------
READ = [
    "/api/health",
    "/api/dashboard/summary",
    "/api/jobs",
    "/api/models",
    "/api/languages",
    "/api/profiles",
    "/api/providers",
    "/api/provider-config",
    "/api/library?page=1&limit=5",
    "/api/analytics/overview",
    "/api/settings",
    "/api/logs",
    "/api/glossaries",
    "/api/memory/search",
    "/api/reader/settings",
    "/api/account/portal",
    "/api/account/marketplace",
    "/api/account/orders",
    "/api/account/business-requests",
    "/api/account/api-keys",
]

results = {}
print("=== read-only endpoints ===")
print("-" * 70)
for path in READ:
    status, body = get(path)
    results[path] = {"status": status, "shape": shape(body)}
    flag = "ok " if status == 200 else "!! "
    print(f"  {flag}{status}  {path}")
    if status != 200:
        print(f"        {json.dumps(body, ensure_ascii=False)[:110]}")

# --- per-job endpoints, using a real job ---------------------------------
jobs = get("/api/jobs")[1]
items = jobs.get("items", []) if isinstance(jobs, dict) else []
job_id = items[0]["id"] if items else None
print()
print("=== per-job endpoints ===")
print("-" * 70)
if job_id:
    for suffix in ["", "/chunks", "/logs"]:
        path = f"/api/jobs/{job_id}{suffix}"
        status, body = get(path)
        results[path] = {"status": status, "shape": shape(body)}
        print(f"  {'ok ' if status == 200 else '!! '}{status}  {path}")
else:
    print("  no jobs in the database; per-job endpoints skipped")

# --- reader endpoints, against a job that produced output -----------------
print()
print("=== reader endpoints ===")
print("-" * 70)
# `job.reader` is a PATH ("/reader/<id>"), not a bare id. Interpolating it into
# f"/api/reader/{reader_id}" produced "/api/reader//reader/..." and a 404 that
# looked like a missing endpoint.
reader_path = next((job["reader"] for job in items if job.get("reader")), None)
if reader_path:
    print(f"  (job.reader is a path: {reader_path!r})")
    for suffix in ["/chapters", "/chapters/1", "/chapters/1/blocks"]:
        path = f"/api{reader_path}{suffix}"
        status, body = get(path)
        results[path] = {"status": status, "shape": shape(body)}
        print(f"  {'ok ' if status == 200 else '!! '}{status}  {path}")
else:
    print("  no job exposes a reader path yet")

# --- endpoints the front end will want but may not exist -----------------
print()
print("=== gaps: what Phase 3-5 will need ===")
print("-" * 70)

# Take a real book id from the list rather than assuming 1 exists.
library = get("/api/library?page=1&limit=5")[1]
library_items = library.get("items", []) if isinstance(library, dict) else []
LIBRARY_ID = library_items[0]["id"] if library_items else 0
print(f"  (using real book id: {LIBRARY_ID!r} from {len(library_items)} item(s))")
GAPS = [
    ("library detail", f"/api/library/{LIBRARY_ID}"),
    ("library list", "/api/library?page=1&limit=5"),
    ("library books", f"/api/library/{LIBRARY_ID}/books"),
    ("library upload/start", f"/api/library/{LIBRARY_ID}/translate"),
    ("book glossary", f"/api/library/{LIBRARY_ID}/glossary?from=EN&to=FA"),
    ("glossary proposal draft", f"/api/library/{LIBRARY_ID}/glossary/proposal?origin=preflight"),
    ("account api-key create", "/api/account/api-keys"),
    ("settings write", "/api/settings"),
]

for label, path in GAPS:
    status, body = get(path)
    marker = "ok " if status < 400 else "!! "
    note = ""
    if status == 405 or (isinstance(body, dict) and "__text" in body):
        note = "  <-- exists but not GET (fine for a write)"
    elif status >= 400:
        note = "  <-- MISSING or rejected"
    print(f"  {marker}{status}  {label:26} {path}{note}")
    results[path] = {"status": status, "shape": shape(body), "label": label}

(OUT / "shapes.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)

print()
print(f"wrote {OUT / 'shapes.json'}")
print(f"{len(results)} endpoint(s) recorded")
