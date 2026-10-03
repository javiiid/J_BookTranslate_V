"""End-to-end check that the cross-origin guard actually blocks the attack.

Part 1 replays the exact request that returned 201 Created before the fix.
Part 2 confirms the app still works for a legitimate same-origin caller.
Part 3 confirms the rows the attack would have created do not exist.
"""
import json
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8765"
EVIL = "https://attacker.example"


def call(method, path, *, body=None, content_type=None, origin=EVIL, host=None,
         fetch_site=None):
    headers = {}
    if origin is not None:
        headers["Origin"] = origin
    if content_type:
        headers["Content-Type"] = content_type
    if host:
        headers["Host"] = host
    if fetch_site:
        headers["Sec-Fetch-Site"] = fetch_site
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read()[:200].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:200].decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)[:160]


for _ in range(20):
    try:
        urllib.request.urlopen(BASE + "/api/health", timeout=1)
        break
    except Exception:  # noqa: BLE001
        time.sleep(0.5)

failures = 0

print("PART 1 - the attack (must be refused with 403)")
print("-" * 66)
attacks = [
    ("POST", "/api/account/api-keys", json.dumps({"name": "evil-key"}).encode(),
     "text/plain;charset=UTF-8", "text/plain is a CORS simple request"),
    ("POST", "/api/account/api-keys", json.dumps({"name": "evil-key"}).encode(),
     "application/json", "correct content type, foreign origin"),
    ("POST", "/api/account/checkout", json.dumps({"kind": "credits", "reference_id": "creator"}).encode(),
     "text/plain;charset=UTF-8", "billing write"),
    ("POST", "/api/account/business-requests",
     json.dumps({"request_type": "enterprise", "contact_name": "e", "email": "a@b.c"}).encode(),
     "text/plain;charset=UTF-8", "business request"),
]
for method, path, body, ctype, why in attacks:
    status, text = call(method, path, body=body, content_type=ctype)
    ok = status == 403
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {status}  {path:34} ({why})")

print()
print("  forged Sec-Fetch-Site must also be refused")
status, text = call("POST", "/api/account/api-keys", body=json.dumps({"name": "x"}).encode(),
                    content_type="application/json", origin=None, fetch_site="cross-site")
ok = status == 403
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} {status}  Sec-Fetch-Site: cross-site")

print()
print("PART 2 - the legitimate app (must still work)")
print("-" * 66)
legit = [
    ("GET", "/api/health", None, None),
    ("GET", "/api/jobs", None, None),
    ("POST", "/api/account/api-keys", json.dumps({"name": "legit-key"}).encode(),
     "application/json"),
]
for method, path, body, ctype in legit:
    status, text = call(method, path, body=body, content_type=ctype,
                        origin="http://127.0.0.1:8765", fetch_site="same-origin")
    ok = status in (200, 201)
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {status}  {method:5} {path}")

print()
print("  DNS rebinding: a foreign Host must be refused")
status, _ = call("GET", "/api/jobs", origin=None, host="attacker.example")
ok = status == 403
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} {status}  GET /api/jobs  Host: attacker.example")

print()
print("PART 3 - no attack rows exist in the database")
print("-" * 66)
sys.path.insert(0, r"D:\J_BookTranslate_V")
from app.storage.database import db  # noqa: E402

evil = db.fetch_one("SELECT COUNT(*) AS n FROM account_api_keys WHERE name='evil-key'")["n"]
ok = evil == 0
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} evil-key rows: {evil}")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
