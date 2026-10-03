"""Finish the JobDetailPage migration: class names, not just token names.

The previous script renamed `var(--old)` to `var(--new)`, but the buttons, tabs
and toasts were hand-written class names (`btn-primary`, `rounded-full ...`)
and the import of the removed `BADGE_CLASS`. Those are updated here.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

path = Path(r"D:\J_BookTranslate_V\frontend\ui\src\pages\JobDetailPage.tsx")
text = path.read_text(encoding="utf-8")
original = text

# The tone-aware helper replaced the flat BADGE_CLASS map.
text = text.replace(
    "import { BADGE_CLASS, STATUS_FA, fa } from '@/lib/format'",
    "import { STATUS_FA, badgeClass, fa } from '@/lib/format'",
)

# The status chip is now the token-driven badge, not a rounded pill with a
# per-status Tailwind string baked in.
text = re.sub(
    r'<span className=\{`rounded-full border px-2\.5 py-1 text-\[11px\] font-bold \$\{BADGE_CLASS\[data\.status\]\}`\}\s*>\s*\{STATUS_FA\[data\.status\]\}',
    '<span className={badgeClass(data.status)}>{STATUS_FA[data.status]}',
    text,
)

# Buttons: `btn` carries the shared shape, the variant carries the intent.
text = text.replace('className="btn-secondary"', 'className="btn btn-secondary"')
text = text.replace('className="btn-primary"', 'className="btn btn-primary"')
text = text.replace('className="btn-danger"', 'className="btn btn-danger"')

# Toast now selects its tone by class rather than an inline background.
text = re.sub(
    r'className="toast"\s*\n(\s*)style=\{\{\s*\n\s*background: tone === \'ok\' \? \'var\(--color-success\)\' : \'var\(--color-error\)\',\s*\n\s*color: \'var\(--color-text-inverse\)\',\s*\n\s*\}\}',
    r'className={`toast ${tone === \'ok\' ? \'toast-ok\' : \'toast-error\'}`}',
    text,
)

# The tab strip is a named component now.
text = text.replace(
    'className="mb-5 flex gap-4 border-b" style={{ borderColor: \'var(--color-border)\' }}',
    'className="tab-list mb-5"',
)

# Typography and padding now come from the scale.
text = text.replace('className="px-6 py-8"', 'className="py-8"')
text = text.replace(
    'className="truncate text-2xl font-extrabold tracking-tight"',
    'className="truncate text-[length:var(--text-h1)] font-extrabold tracking-tight"',
)
text = text.replace('className="mt-1 text-xs"', 'className="mt-1 text-[length:var(--text-caption)]"')
text = text.replace('className="text-xs"', 'className="text-[length:var(--text-caption)]"')
text = text.replace('className="text-base font-extrabold"', 'className="text-[length:var(--text-h3)] font-extrabold"')
text = text.replace('className="text-lg font-extrabold"', 'className="text-[length:var(--text-h2)] font-extrabold"')
text = text.replace('className="text-sm"', 'className="text-[length:var(--text-small)]"')
text = text.replace('className="text-xs font-bold tabular-nums"', 'className="text-[length:var(--text-small)] font-bold tabular-nums"')
text = text.replace('className="ms-1 text-[10px] tabular-nums"', 'className="ms-1 text-[length:var(--text-caption)] tabular-nums"')
text = text.replace('className="mb-5"', 'className="mb-5"')

if text == original:
    print("nothing changed -- check the anchors")
    raise SystemExit(1)

path.write_text(text, encoding="utf-8")

print("=== leftovers from the old naming ===")
for name, pattern in [
    ("BADGE_CLASS", r"BADGE_CLASS"),
    ("rounded-full pill badge", r"rounded-full border px-2\.5"),
    ("inline toast background", r"background: tone ==="),
    ("tab strip inline style", r"flex gap-4 border-b"),
    ("bare btn-primary (no .btn)", r'className="btn-primary"'),
    ("old px-6 page padding", r'className="px-6 py-8"'),
    ("old text-2xl scale", r"text-2xl font-extrabold"),
]:
    found = re.findall(pattern, text)
    print(f"  {name:28} {len(found)} occurrence(s)" + ("  <-- still there" if found else ""))
