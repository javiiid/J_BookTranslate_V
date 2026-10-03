"""Finish the design-system migration across every remaining component.

The token rename was mechanical; this handles the *class names*, which is where
the design decisions live:

  text-2xl / text-lg / text-base / text-sm / text-xs / text-[11px]
      -> the --text-* scale, so type sizes stop being arbitrary

  btn-primary / btn-secondary / btn-danger
      -> `btn btn-*`: the shared shape plus the intent

  rounded-xl / rounded-2xl / rounded-full on cards and fields
      -> the --radius-* scale. The brief asks for restraint, and 20px cards
         read as toy-like; fields move to --radius-control.

  ad-hoc inline borders and backgrounds
      -> named component classes where one already exists (alert, field,
         progress-track, data-label, tab-list), so the palette stays in CSS

Every replacement is reported, and anything still matching an old pattern is
listed at the end rather than left to be discovered in the browser.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

UI = Path(r"D:\J_Translate_Ui\ui")
files = sorted((UI / "src").rglob("*.tsx"))

# Ordered longest-first where patterns overlap.
REPLACEMENTS: list[tuple[str, str]] = [
    # --- typography -> the scale ---
    (r'text-\[length:var\(--text-h1\)\]', None),  # already done, keep
    (r'\btext-2xl\b', 'text-[length:var(--text-h1)]'),
    (r'\btext-lg\b', 'text-[length:var(--text-h2)]'),
    (r'\btext-base\b', 'text-[length:var(--text-h3)]'),
    (r'\btext-sm\b', 'text-[length:var(--text-small)]'),
    (r'\btext-xs\b', 'text-[length:var(--text-label)]'),
    (r'text-\[13px\]', 'text-[length:var(--text-small)]'),
    (r'text-\[12px\]', 'text-[length:var(--text-small)]'),
    (r'text-\[12\.5px\]', 'text-[length:var(--text-small)]'),
    (r'text-\[11px\]', 'text-[length:var(--text-caption)]'),
    (r'text-\[10px\]', 'text-[length:var(--text-caption)]'),

    # --- buttons: shared shape + intent ---
    (r'className="btn-primary"', 'className="btn btn-primary"'),
    (r'className="btn-secondary"', 'className="btn btn-secondary"'),
    (r'className="btn-danger"', 'className="btn btn-danger"'),

    # --- radius scale ---
    (r'\brounded-2xl\b', 'rounded-[var(--radius-card)]'),
    (r'\brounded-xl\b', 'rounded-[var(--radius-control)]'),
    # progress bars legitimately stay fully rounded
    (r'h-2\.5 w-full overflow-hidden rounded-full', 'progress-track w-full'),
    (r'h-full rounded-full transition-\[width\] duration-500', 'progress-fill'),

    # --- form controls -> the shared field class ---
    (r'className="min-w-\[220px\] flex-1 rounded-\[var\(--radius-control\)\] border px-3 py-2 text-\[length:var\(--text-small\)\]"',
     'className="field min-w-[220px] flex-1"'),
    (r'className="rounded-\[var\(--radius-control\)\] border px-3 py-2 text-\[length:var\(--text-small\)\]"',
     'className="field"'),

    # --- alerts: one class instead of an inline border + colour ---
    (r'<p role="alert" className="text-\[length:var\(--text-small\)\]" style=\{\{ color: \'var\(--color-error\)\' \}\}>',
     '<p role="alert" className="alert alert-error">'),

    # --- data labels ---
    (r'<span className="block text-\[length:var\(--text-caption\)\]" style=\{\{ color: \'var\(--color-text-muted\)\' \}\}>',
     '<span className="data-label">'),
    (r'<span className="mt-1 block truncate text-\[length:var\(--text-small\)\]" style=\{\{ color: \'var\(--color-text-muted\)\' \}\}>',
     '<span className="data-label">'),

    # --- spacing from the scale where it was arbitrary px ---
    (r'\bmt-1\b', 'mt-[var(--spacing-1)]'),
    (r'\bmt-2\b', 'mt-[var(--spacing-2)]'),
    (r'\bmt-3\b', 'mt-[var(--spacing-3)]'),
    (r'\bmt-4\b', 'mt-[var(--spacing-4)]'),
    (r'\bmt-5\b', 'mt-[var(--spacing-5)]'),
    (r'\bmb-3\b', 'mb-[var(--spacing-3)]'),
    (r'\bmb-4\b', 'mb-[var(--spacing-4)]'),
    (r'\bmb-5\b', 'mb-[var(--spacing-5)]'),
    (r'\bmb-6\b', 'mb-[var(--spacing-6)]'),
    (r'\bp-3\b', 'p-[var(--spacing-3)]'),
    (r'\bp-4\b', 'p-[var(--spacing-4)]'),
    (r'\bp-5\b', 'p-[var(--spacing-5)]'),
    (r'\bpy-8\b', 'py-[var(--spacing-8)]'),
    (r'\bgap-3\b', 'gap-[var(--spacing-3)]'),
    (r'\bgap-4\b', 'gap-[var(--spacing-4)]'),
]

counts: dict[str, int] = {}
for path in files:
    text = path.read_text(encoding="utf-8")
    original = text
    for pattern, replacement in REPLACEMENTS:
        if replacement is None:
            continue
        text, n = re.subn(pattern, replacement, text)
        if n:
            counts[pattern] = counts.get(pattern, 0) + n
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"  {path.relative_to(UI)}")

print("\n=== replacements ===")
for pattern, n in sorted(counts.items(), key=lambda kv: -kv[1]):
    print(f"  {n:>3}x  {pattern[:66]}")

print("\n=== anything still on the old patterns ===")
OLD = re.compile(
    r'\btext-(xs|sm|base|lg|2xl|xl)\b|text-\[1[0-3](?:\.5)?px\]|'
    r'className="btn-(primary|secondary|danger)"|\brounded-(xl|2xl|3xl)\b|'
    r'color: #fff|bg-white|text-white'
)
found = False
for path in files:
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if OLD.search(line):
            print(f"  {path.relative_to(UI)}:{index}  {line.strip()[:80]}")
            found = True
if not found:
    print("  none")
