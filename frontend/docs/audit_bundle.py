"""Pre-flight check on the built bundle, for the day Python serves dist/.

Phase 6 is "serve dist/ from Python and delete the old templates". That is the
one irreversible step in the migration, and three things in a Vite bundle would
break silently if the backend serves it wrongly:

  1. Hash-named assets under /assets/ need the right MIME type. A JS file
     served as text/plain is refused by the browser with a CSP error, and the
     page renders as a blank white screen with no error in the app's own logs.
  2. The bundle inlines /api calls as absolute paths. If the app is ever mounted
     under a prefix, those break.
  3. The Reader uses dangerouslySetInnerHTML on server-sanitised HTML. If the
     served response carries a CSP, the policy has to allow the images the
     backend serves as local assets, or chapter illustrations vanish.

This does not make the decision; it reports what the decision will need.
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

UI = Path(r"D:\J_Translate_Ui\ui")
DIST = UI / "dist"

if not DIST.is_dir():
    print(f"  {DIST} does not exist; run `npm run build` first")
    raise SystemExit(1)

index = DIST / "index.html"
html = index.read_text(encoding="utf-8")

print("=== what the entry HTML references ===")
print("-" * 70)
refs = re.findall(r'(?:src|href)="([^"]+)"', html)
for ref in refs:
    print(f"  {ref}")

print()
print("=== absolute vs relative asset paths ===")
print("-" * 70)
absolute = [r for r in refs if r.startswith("http://") or r.startswith("https://")]
rooted = [r for r in refs if r.startswith("/")]
relative = [r for r in refs if not r.startswith(("/", "http"))]
print(f"  absolute (external origin) : {len(absolute)}  {absolute}")
print(f"  root-relative (/assets/..) : {len(rooted)}  {rooted}")
print(f"  document-relative         : {len(relative)}  {relative}")
print("  -> root-relative means the app must be served at the origin root.")

print()
print("=== API paths baked into the bundle ===")
print("-" * 70)
bundle_files = list((DIST / "assets").glob("*.js"))
api_paths = set()
for path in bundle_files:
    text = path.read_text(encoding="utf-8", errors="ignore")
    api_paths.update(re.findall(r'["\'`](/api/[a-z0-9_/{}$.\-]+)', text))
for found in sorted(api_paths):
    print(f"  {found}")
print(f"  {len(api_paths)} distinct /api path(s). All are root-relative.")

print()
print("=== reader asset URLs, which the CSP must permit ===")
print("-" * 70)
for path in bundle_files:
    text = path.read_text(encoding="utf-8", errors="ignore")
    for match in set(re.findall(r'["\'`](/reader/[^"\'`\s]{0,40})', text)):
        print(f"  {match}")
print("  The Reader injects server-sanitised HTML that references /reader/<id>/asset/<path>.")
print("  A CSP without img-src 'self' would blank every chapter illustration.")

print()
print("=== bundle contents ===")
print("-" * 70)
total = 0
for path in sorted(DIST.rglob("*")):
    if path.is_file():
        size = path.stat().st_size
        total += size
        relative = path.relative_to(DIST)
        flag = ""
        if path.suffix == ".map":
            flag = "  <- sourcemap: do NOT serve in production"
        print(f"  {relative.as_posix():<44} {size / 1024:>9.1f} KB{flag}")
print(f"  {'TOTAL':<44} {total / 1024:>9.1f} KB")

print()
print("=== what Phase 6 would need from app/web.py ===")
print("-" * 70)
for item in [
    "a GET route for /assets/* with the right MIME type and a long max-age",
    "a catch-all that serves index.html for unknown non-API paths (SPA history)",
    "a CSP header that allows img-src 'self' and the reader asset route",
    "a decision on /workspace, /library, /account: React or Python, not both",
    "a redirect so the old Python pages are not reachable by two URLs",
]:
    print(f"  - {item}")

print()
print("Nothing is changed here. This is a report.")
