"""Save the live payloads the contrast audit renders against.

Captured from the running backend rather than hand-written, so the audit renders
the same data the browser would receive. Written to `ui/scripts/page-data.json`,
which is gitignored: it is a snapshot of one user's library, and it contains
book titles and job ids.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8765"
OUT = Path(r"D:\J_Translate_Ui\ui\scripts\page-data.json")
READER = "/reader/040061b0658b"

for _ in range(30):
    try:
        urllib.request.urlopen(f"{BASE}/api/health", timeout=1)
        break
    except Exception:  # noqa: BLE001
        time.sleep(0.5)


def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=20) as response:
        return json.loads(response.read())


jobs = get("/api/jobs")["items"]
reader_path = next((j["reader"] for j in jobs if j.get("reader")), None)

payloads = {
    "/api/health": get("/api/health"),
    "/api/dashboard/summary": get("/api/dashboard/summary"),
    "/api/jobs": get("/api/jobs"),
    "/api/models": get("/api/models"),
    "/api/languages": get("/api/languages"),
    "/api/provider-config": get("/api/provider-config"),
    "/api/account/portal": get("/api/account/portal"),
    "/api/analytics/overview": get("/api/analytics/overview"),
    "/api/reader/settings": get("/api/reader/settings"),
}

if reader_path:
    chapters = get(f"/api{reader_path}/chapters")["items"]
    first = chapters[0]["id"]
    payloads[f"/api{reader_path}/chapters"] = get(f"/api{reader_path}/chapters")
    payloads[f"/api{reader_path}/chapters/{first}"] = get(f"/api{reader_path}/chapters/{first}")
    payloads[f"/api{reader_path}/chapters/{first}/blocks"] = get(
        f"/api{reader_path}/chapters/{first}/blocks"
    )

OUT.write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
print(f"wrote {OUT}  ({OUT.stat().st_size / 1024:.1f} KB, {len(payloads)} payload(s))")
for key in payloads:
    print(f"  {key}")
