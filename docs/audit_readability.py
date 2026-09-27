"""Fetch the real Reader and Account payloads and audit them for readability.

"the text is not readable" is a contrast complaint, and there are two very
different places it can come from:

  1. the chapter HTML arriving from the Python `sanitize_html` boundary, which
     may still carry the source book's own colours
  2. the React page's own token choices

So this pulls the real payloads and looks at the inline styles and colours
inside them, rather than reasoning about what the page "should" render.
"""
import json
import re
import sys
import time
import urllib.request
from collections import Counter

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
reader_path = next((j["reader"] for j in jobs if j.get("reader")), None)
print(f"=== reader path: {reader_path} ===")

if not reader_path:
    print("  no job exposes a reader")
    raise SystemExit(1)

chapters = get(f"/api{reader_path}/chapters")["items"]
print(f"  {len(chapters)} chapter(s): {[c['title'] for c in chapters][:4]}")

chapter = get(f"/api{reader_path}/chapters/{chapters[0]['id']}")
blocks = get(f"/api{reader_path}/chapters/{chapters[0]['id']}/blocks")["items"]

html = chapter["html"]
print(f"\n  chapter html: {len(html)} chars")

print()
print("=== inline styles inside the sanitised chapter HTML ===")
print("-" * 72)
styles = re.findall(r'style="([^"]*)"', html)
print(f"  {len(styles)} style attribute(s)")
for style, count in Counter(styles).most_common(10):
    print(f"  x{count:<3} {style[:96]}")

print()
print("=== colour declarations in the chapter HTML ===")
print("-" * 72)
colours = re.findall(r"(?:color|background|background-color)\s*:\s*([^;\"]+)", html, re.I)
if colours:
    for value, count in Counter(c.strip().lower() for c in colours).most_common(12):
        print(f"  x{count:<3} {value}")
else:
    print("  none -- the HTML carries no colours of its own")

print()
print("=== tags present ===")
print("-" * 72)
tags = Counter(t.lower() for t in re.findall(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9]*)", html))
print("  " + ", ".join(f"{t}x{c}" for t, c in tags.most_common(14)))

print()
print("=== the bilingual blocks ===")
print("-" * 72)
if blocks:
    block = blocks[0]
    for field in ("original_html", "translation_html"):
        value = block[field]
        found = re.findall(r"(?:color|background)\s*:\s*([^;\"]+)", value, re.I)
        print(f"  {field}: {len(value)} chars, {len(found)} colour declaration(s)")
        for item in Counter(f.strip().lower() for f in found).most_common(4):
            print(f"      x{item[1]} {item[0]}")
    print()
    print("  a sample of original_html:")
    print("   ", block["original_html"][:300])
else:
    print("  no blocks -- the bilingual view will fall back to the chapter html")

print()
print("=== account payload ===")
print("-" * 72)
portal = get("/api/account/portal")
overview = portal["overview"]
account = overview["account"]
print(f"  display_name : {account['display_name']!r}")
print(f"  plan         : {account['plan']!r}")
print(f"  organization : {account['organization']!r}")
print(f"  counts       : {overview['counts']}")
print(f"  transactions : {len(overview['transactions'])}")
if overview["transactions"]:
    t = overview["transactions"][0]
    print(f"  first txn    : kind={t['kind']!r} status={t['status']!r} ref={t['reference_id']!r}")
    print(f"                 amount_usd={t['amount_usd']!r} credits={t['credits']!r}")

analytics = get("/api/analytics/overview")
print(f"  analytics    : {analytics}")
config = get("/api/provider-config")
print(f"  provider     : {config}")
