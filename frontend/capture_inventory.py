"""Phase 0 - capture the CURRENT rendered UI as the migration reference.

The Python pages are assembled through chains of ``PAGE.replace(...)`` calls, so
the Python source is NOT a reliable description of what the user sees. This
script snapshots the actual served HTML for every route so the port can be
checked against a concrete "before".
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8765"
OUT = Path(r"D:\J_BookTranslate_V\frontend\docs\inventory")
OUT.mkdir(parents=True, exist_ok=True)

JOB = "040061b0658b"

PAGES = [
    ("welcome", "/"),
    ("landing", "/landing"),
    ("workspace", "/workspace"),
    ("library", "/library"),
    ("reader", f"/reader/{JOB}"),
    ("account", "/account"),
    ("job-monitor", f"/workspace/job/{JOB}"),
]

APIS = [
    "/api/health",
    "/api/dashboard/summary",
    "/api/jobs",
    "/api/models",
    "/api/languages",
    "/api/library",
    "/api/glossaries",
    "/api/analytics/overview",
    "/api/reader/settings",
    f"/api/reader/{JOB}/chapters",
    f"/api/reader/{JOB}/chapters/2",
    f"/api/reader/{JOB}/chapters/2/blocks",
    f"/api/jobs/{JOB}",
    f"/api/jobs/{JOB}/chunks",
    f"/api/jobs/{JOB}/logs",
]


def get(path):
    try:
        with urllib.request.urlopen(f"{BASE}{path}") as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001 - inventory must not crash
        return 0, str(exc).encode("utf-8", "replace")


manifest = {"base": BASE, "job": JOB, "pages": {}, "apis": {}}

for name, path in PAGES:
    status, body = get(path)
    (OUT / f"page-{name}.html").write_bytes(body)
    text = body.decode("utf-8", "replace")
    manifest["pages"][name] = {
        "path": path,
        "status": status,
        "bytes": len(body),
        "title": (text.split("<title>")[1].split("</title>")[0] if "<title>" in text else ""),
    }
    print(f"page  {name:12} {status}  {len(body):>8} bytes  {manifest['pages'][name]['title'][:40]}")

print()
for path in APIS:
    status, body = get(path)
    try:
        parsed = json.loads(body)
        shape = (
            f"list[{len(parsed['items'])}]"
            if isinstance(parsed, dict) and isinstance(parsed.get("items"), list)
            else f"keys={sorted(parsed)[:8]}" if isinstance(parsed, dict) else type(parsed).__name__
        )
    except Exception:  # noqa: BLE001
        shape = "<non-json>"
    (OUT / ("api" + path.replace("/", "_") + ".json")).write_bytes(body)
    manifest["apis"][path] = {"status": status, "shape": shape}
    print(f"api   {status}  {path:46} {shape}")

(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nmanifest -> {OUT / 'manifest.json'}")
