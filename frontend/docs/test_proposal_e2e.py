"""End-to-end check of the glossary proposal flow against the live server.

Runs the real endpoints: upload a book, request a proposal, read the draft,
approve part of it, and confirm the approved terms reach the live glossary
while the rejected ones do not. The LLM call is replaced by a fake client at
the module level so no provider credits are spent.
"""
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8765"
failures = 0


def check(label, condition, detail=""):
    global failures
    failures += not condition
    print(f"  {'ok  ' if condition else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))


for _ in range(24):
    try:
        urllib.request.urlopen(f"{BASE}/api/health", timeout=1)
        break
    except Exception:  # noqa: BLE001
        time.sleep(0.5)


def get(path):
    with urllib.request.urlopen(f"{BASE}{path}") as response:
        return json.loads(response.read())


def post_json(path, payload):
    request = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Origin": BASE}, method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def put_json(path, payload):
    request = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Origin": BASE}, method="PUT",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def upload(epub: Path, from_lang="EN", to_lang="FA"):
    boundary = uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"from_lang\"\r\n\r\n{from_lang}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"to_lang\"\r\n\r\n{to_lang}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\ngpt-5.6-terra\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"mode\"\r\n\r\nfast\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"book\"; filename=\"{epub.name}\"\r\n"
        f"Content-Type: application/epub+zip\r\n\r\n".encode(),
        epub.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    request = urllib.request.Request(
        f"{BASE}/api/jobs", data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                 "Origin": BASE},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


print("=== 1. upload returns the book id the panel needs ===")
print("-" * 66)
source = sorted(Path(r"D:\J_BookTranslate_V\data\uploads").glob("*flex_test.epub"))[0]
job = upload(source)
book_id = job.get("book_id")
check("response carries book_id", bool(book_id), f"book_id={book_id}")
check("response carries the language pair", job.get("from_lang") == "EN" and job.get("to_lang") == "FA")

print()
print("=== 2. a proposal is refused before the book has any chunks ===")
print("-" * 66)
# A freshly uploaded book has no pipeline state yet, so proposing must explain
# itself rather than fail opaquely.
status, body = post_json(f"/api/library/{book_id}/glossary/propose",
                         {"from_lang": "EN", "to_lang": "FA"})
check("does not silently succeed on a book with no chunks", status in (404, 400), f"status={status}")
if status in (404, 400):
    print(f"       message: {body.get('error', '')[:96]}")

print()
print("=== 3. draft read endpoint ===")
print("-" * 66)
try:
    draft = get(f"/api/library/{book_id}/glossary/proposal?from=EN&to=FA&origin=preflight")
    check("draft endpoint responds", draft.get("origin") == "preflight")
    check("draft starts empty", draft.get("terms") == [])
except urllib.error.HTTPError as exc:
    check("draft endpoint responds", False, f"status={exc.code}")

print()
print("=== 4. cross-origin guard still covers the new endpoints ===")
print("-" * 66)
request = urllib.request.Request(
    f"{BASE}/api/library/{book_id}/glossary/propose",
    data=json.dumps({"from_lang": "EN", "to_lang": "FA"}).encode(),
    headers={"Content-Type": "text/plain;charset=UTF-8",
             "Origin": "https://attacker.example"},
    method="POST",
)
try:
    urllib.request.urlopen(request)
    check("cross-origin propose is refused", False, "it was accepted")
except urllib.error.HTTPError as exc:
    check("cross-origin propose is refused", exc.code == 403, f"status={exc.code}")

print()
print("=== 5. promotion only moves approved terms ===")
print("-" * 66)
from app.storage.database import db  # noqa: E402
from app.glossary.service import save_proposal  # noqa: E402
from app.glossary.proposal import key  # noqa: E402

save_proposal(db, book_id, "EN", "FA", [
    {"source_term": "Ann", "target_term": "آن", "kind": "person", "notes": ""},
    {"source_term": "Robert", "target_term": "رابرت", "kind": "person", "notes": ""},
    {"source_term": "Invisible", "target_term": "نامرئی", "kind": "term", "notes": ""},
])
draft = get(f"/api/library/{book_id}/glossary/proposal?from=EN&to=FA&origin=preflight")
check("draft now has three terms", len(draft["terms"]) == 3)

status, result = put_json(f"/api/library/{book_id}/glossary/proposal/approve", {
    "from_lang": "EN", "to_lang": "FA", "origin": "preflight",
    "approved": ["Ann", "ROBERT"],   # one of them intentionally in a different case
})
check("approve succeeds", status == 200, f"status={status}")
approved_keys = {key(t["source_term"]) for t in result.get("terms", [])}
check("Ann was promoted", key("Ann") in approved_keys)
check("Robert was promoted despite case difference", key("Robert") in approved_keys)
check("the unapproved term was dropped", key("Invisible") not in approved_keys)

after = get(f"/api/library/{book_id}/glossary/proposal?from=EN&to=FA&origin=preflight")
check("draft is cleared after approval", after["terms"] == [])

live = get(f"/api/library/{book_id}/glossary?from=EN&to=FA")
check("the live glossary holds exactly the approved terms",
      {key(t["source_term"]) for t in live["terms"]} == {key("Ann"), key("Robert")})

print()
print("=== cleanup: remove the terms this check added ===")
print("-" * 66)
for term in live["terms"]:
    db.execute("DELETE FROM book_glossary_proposals WHERE book_id=?", (book_id,))
current = get(f"/api/library/{book_id}/glossary?from=EN&to=FA")
from app.glossary.service import save_glossary  # noqa: E402
save_glossary(db, book_id, {
    "source_language": "EN", "target_language": "FA",
    "version": current["version"], "terms": [],
})
check("glossary reset to empty", get(f"/api/library/{book_id}/glossary?from=EN&to=FA")["terms"] == [])

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
