"""Dump the raw chapter HTML so the markup can be read directly.

The tag census reported tags named `px` and `ax`, which no HTML contains. That
is either a broken sanitiser or a broken census, and the difference matters: a
mangled document renders as visible garbage, while a bad regex only misleads me.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8765"

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
reader_path = next(j["reader"] for j in jobs if j.get("reader"))
chapters = get(f"/api{reader_path}/chapters")["items"]
chapter = get(f"/api{reader_path}/chapters/{chapters[0]['id']}")

html = chapter["html"]
out = Path(r"D:\J_Translate_Ui\docs\reader-chapter.html")
out.write_text(html, encoding="utf-8")

print("=== the first 1200 characters, verbatim ===")
print("-" * 72)
print(repr(html[:1200]))

print()
print("=== every opening tag, in order ===")
print("-" * 72)
for index, tag in enumerate(re.findall(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9-]*)", html)):
    print(f"  {index:3}  {tag}")

print()
print("=== where does 'px' come from? ===")
print("-" * 72)
for match in re.finditer(r"<\s*/?\s*px", html):
    start = max(0, match.start() - 60)
    print(f"  at {match.start()}: ...{html[start:match.start() + 60]!r}")

print()
print("=== is any tag left unclosed? ===")
print("-" * 72)
stack = []
void = {"br", "hr", "img", "meta", "link", "input", "source"}
for match in re.finditer(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9-]*)[^>]*?(/?)>", html):
    closing, name, self_closing = match.group(1), match.group(2).lower(), match.group(3)
    if name in void or self_closing:
        continue
    if closing:
        if stack and stack[-1] == name:
            stack.pop()
        else:
            print(f"  stray </{name}>; open stack: {stack}")
    else:
        stack.append(name)
print(f"  unclosed at end: {stack or 'none'}")
