"""Enumerate the real routes and page handlers for the README.

Rather than transcribing what I remember, this reads the routing conditions so
the route table in the README matches the code. Anything it cannot find is
reported as unknown instead of being guessed.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\J_BookTranslate_V")

files = [
    ROOT / "app" / "web.py",
    ROOT / "app" / "jobs" / "detail_page.py",
    ROOT / "app" / "reader" / "service.py",
    ROOT / "app" / "library" / "view.py",
    ROOT / "app" / "account" / "page.py",
    ROOT / "app" / "welcome" / "page.py",
    ROOT / "app" / "glossary" / "proposal_page.py",
]

# Conditions look like:  path == "/api/x"  or  path.startswith('/api/y')
CONDITION = re.compile(
    r"(?:path|parsed\.path)\s*(?:==|\.startswith\()\s*[\"']([^\"']+)[\"']"
)

print("=== routes found in code ===\n")
seen = set()
for path in files:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for match in CONDITION.finditer(text):
        route = match.group(1)
        if route in seen or len(route) < 2:
            continue
        seen.add(route)
        line = text[: match.start()].count("\n") + 1
        print(f"  {route:52} {path.name}:{line}")

print(f"\n  total: {len(seen)}")

print()
print("=== the port the server binds ===")
web = (ROOT / "app" / "web.py").read_text(encoding="utf-8", errors="ignore")
for match in re.finditer(r"(\d{4,5})\s*(?:,\s*)?(?:HTTPServer|ThreadingHTTPServer)", web):
    print(f"  port {match.group(1)}")
for match in re.finditer(r"DEFAULT_PORT\s*=\s*(\d+)", web):
    print(f"  DEFAULT_PORT = {match.group(1)}")

print()
print("=== models the code knows ===")
models = (ROOT / "app" / "core" / "models.py").read_text(encoding="utf-8", errors="ignore")
block = re.search(r"SUPPORTED_MODELS\s*=\s*\{(.*?)\n\}", models, re.S)
if block:
    for name, desc in re.findall(r'"([^"]+)":\s*\{[^}]*?"description":\s*"([^"]*)"', block.group(1)):
        print(f"  {name:26} {desc}")

print()
print("=== output formats offered by the CLI ===")
out = (ROOT / "app" / "output" / "formats.py").read_text(encoding="utf-8", errors="ignore")
block = re.search(r"OUTPUT_FORMATS\s*[:=]\s*\{(.*?)\n\s*\}", out, re.S)
if block:
    for name in re.findall(r'"([a-z0-9_]+)"\s*:', block.group(1)):
        print(f"  {name}")
