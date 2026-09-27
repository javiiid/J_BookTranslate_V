"""Point elevated surfaces at the border token that works on them.

`--color-border-strong` cannot serve both card surfaces and the dark elevated
surface: on #1F506B a lighter border measures 1.49:1, i.e. invisible, because
the surface is already lighter than the border would be. This edits the single
`.surface-elevated` rule, which is the only place the elevated border is used.

Line-based so CRLF in the file cannot defeat the match.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

path = Path(r"D:\J_Translate_Ui\ui\src\styles\tokens.css")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

changed = 0
inside = False
for index, line in enumerate(lines):
    if ".surface-elevated" in line and "{" in line:
        inside = True
        continue
    if inside and "border:" in line and "var(--color-border)" in line:
        print(f"  line {index + 1}: {line.rstrip()}")
        lines[index] = line.replace("var(--color-border)", "var(--color-border-strong-elevated)")
        print(f"  line {index + 1}: {lines[index].rstrip()}")
        changed += 1
        inside = False
    elif inside and "}" in line:
        inside = False

if changed != 1:
    print(f"changed {changed} site(s); expected exactly 1")
    raise SystemExit(1)

path.write_text("".join(lines), encoding="utf-8")
print("done")
