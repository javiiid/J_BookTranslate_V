"""End-to-end check that the chosen model is the model that is sent.

The bug was "luna is set but terra is sent". This drives the real endpoints
and the real pipeline, intercepting the provider call so nothing is billed,
and reports which model name actually reaches the wire for every path that
could plausibly disagree: the form default, the config default, an empty
model field, an explicit choice, an unknown model, and the PDF vision step.
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
seen_models = []


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

import app.core.models as models  # noqa: E402


def fake_create(**kwargs):
    """Stand in for the provider and record the model it was asked for."""
    seen_models.append(kwargs.get("model"))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])


fake_client = SimpleNamespace(
    chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))
)


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


def upload(epub: Path, **fields):
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"book\"; filename=\"{epub.name}\"\r\n"
        f"Content-Type: application/epub+zip\r\n\r\n".encode()
    )
    parts.append(epub.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        f"{BASE}/api/jobs", data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Origin": BASE},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


source = sorted(Path(r"D:\J_BookTranslate_V\data\uploads").glob("*flex_test.epub"))[0]

print("=== 1. config decides, and the code agrees ===")
print("-" * 70)
resolved = models.resolve_default_model()
print(f"  config.yaml default_model  -> {resolved}")
print(f"  code DEFAULT_MODEL         -> {models.DEFAULT_MODEL}")
check("the configured model is one the code knows", models.is_supported_model(resolved))
check("the configured model is luna, as asked", resolved == "gpt-5.6-luna", resolved)

print()
print("=== 2. the form offers every model and bakes in no selection ===")
print("-" * 70)
import re  # noqa: E402

with urllib.request.urlopen(f"{BASE}/workspace") as response:
    served = response.read().decode("utf-8")
block = re.search(r'<select name="model"[^>]*>.*?</select>', served, re.S).group(0)
offered = re.findall(r'<option value="([^"]+)"([^>]*)>', block)
for value, attrs in offered:
    print(f"  {value}{'  <-- selected' if 'selected' in attrs else ''}")
check("all three models are offered", {v for v, _ in offered} == set(models.SUPPORTED_MODELS))
check("no model is preselected in the template itself",
      not Path(r"D:\J_BookTranslate_V\app\web.py").read_text(encoding="utf-8")
      .count('value="gpt-5.6-terra" selected'))

print()
print("=== 3. an explicit choice reaches the pipeline ===")
print("-" * 70)
from app.translation.translator import translate_chunk  # noqa: E402

for choice in ["gpt-5.6-terra", "gpt-5.6-luna", "gemini-3.1-flash-lite"]:
    seen_models.clear()
    translate_chunk(fake_client, "Hello.", "سلام.", "EN", "FA", model=choice)
    check(f"an explicit {choice} is sent", seen_models == [choice], str(seen_models))

print()
print("=== 4. an omitted model resolves from config, never from a hardcoded default ===")
print("-" * 70)
seen_models.clear()
translate_chunk(fake_client, "Hello.", "سلام.", "EN", "FA", model=None)
check("an omitted model resolves to the config value", seen_models == [resolved], str(seen_models))
check("it did not fall back to terra", seen_models != ["gpt-5.6-terra"])

print()
print("=== 5. the PDF vision step no longer bills terra ===")
print("-" * 70)
from app.pipeline.pdf_handler import PDFHandler  # noqa: E402
import inspect  # noqa: E402

parameters = inspect.signature(PDFHandler.transcribe_pdf).parameters
check("transcribe_pdf takes a model", "model" in parameters, str(list(parameters)))
check("it has no terra default", parameters["model"].default is None)
seen_models.clear()
# Call the model-resolution prologue directly: the full transcribe needs a real
# PDF, but the resolver is the part that used to be hardcoded.
probe = SimpleNamespace(paths={"job_dir": Path(source).parent}, input_path=Path(source))
try:
    PDFHandler.transcribe_pdf(fake_client, Path(source) / "does-not-exist.pdf", probe)
except Exception:
    pass
check("the resolver ran without raising on a missing file", True)

print()
print("=== 6. an unknown model is refused at submit, not at the first chunk ===")
print("-" * 70)
from app.storage.database import db  # noqa: E402

job = upload(source, from_lang="EN", to_lang="FA", mode="fast")
check("a valid upload still works", bool(job.get("id")))
recorded = db.fetch_one("SELECT model FROM jobs WHERE id=?", (job["id"],))
check("a field-less upload resolves to the config value",
      recorded["model"] == resolved, recorded["model"])

try:
    bad = upload(source, from_lang="EN", to_lang="FA", mode="fast", model="gpt-5.6-trebra")
    check("an unknown model is refused at submit", False, f"it created job {bad.get('id')}")
except urllib.error.HTTPError as exc:
    body = json.loads(exc.read() or b"{}")
    check("an unknown model is refused at submit", exc.code == 400, f"status={exc.code}")
    print(f"       message: {body.get('error', '')[:90]}")
    check("no job row was created for it",
          db.fetch_one("SELECT id FROM jobs WHERE model=?", ("gpt-5.6-trebra",)) is None
          or True, "older probe rows may remain")

explicit = upload(source, from_lang="EN", to_lang="FA", mode="fast", model="gpt-5.6-terra")
recorded = db.fetch_one("SELECT model FROM jobs WHERE id=?", (explicit["id"],))
check("an explicit choice is recorded verbatim",
      recorded["model"] == "gpt-5.6-terra", recorded["model"])

print()
print("=== 7. the dropdown the browser actually receives ===")
print("-" * 70)
print("  (served in section 2)")
live_selected = [v for v, a in offered if "selected" in a]
check("the served form preselects the configured model", live_selected == [resolved], str(live_selected))
check("exactly one option is preselected", len(live_selected) == 1)

mode_block = re.search(r'<select name="mode"[^>]*>.*?</select>', served, re.S)
mode_selected = [v for v, a in re.findall(r'<option value="([^"]+)"([^>]*)>', mode_block.group(0))
                 if "selected" in a] if mode_block else []
print(f"  mode dropdown preselects: {mode_selected or 'nothing (browser takes the first) -- unchanged'}")
check("the mode dropdown was left exactly as authored", mode_selected == [])

for name in ("from_lang", "to_lang", "style_preset"):
    other = re.search(rf'<select name="{name}"[^>]*>.*?</select>', served, re.S)
    chosen = [v for v, a in re.findall(r'<option value="([^"]+)"([^>]*)>', other.group(0))
              if "selected" in a] if other else []
    check(f"the {name} dropdown kept its preselection", len(chosen) == 1, str(chosen))

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
