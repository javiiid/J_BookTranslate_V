"""List every distinct string that carries the old product name.

A blind find-and-replace of "KALIMA" is safe for prose but not for
everything: the name appears in HTML titles, in the CLI --help output, in
docstrings that AGENTS.md points developers at, and in test assertions that
check for it. Replacing the wrong one either breaks a test or leaves a stale
string behind.

So the distinct forms are printed first, with where each occurs, and nothing is
edited until the list is read.
"""
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPOS = {
    "python": Path(r"D:\J_BookTranslate_V"),
    "react": Path(r"D:\J_Translate_Ui"),
}

# Anything that could be a rendering of the old name.
PATTERN = re.compile(
    r"J\s*Book\s*Translate|J\s*Translate\s*UI|Translation\s*Studio|"
    r"J_BookTranslate_V|JBT_API|JBT-[A-Za-z]+|j-book-translate",
    re.I,
)

for label, root in REPOS.items():
    print(f"=== {label}: {root} ===")
    forms = Counter()
    sites = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if parts & {"node_modules", ".git", ".venv", "__pycache__", "dist", ".test-tmp", "output", "data", "temp"}:
            continue
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".html", ".md", ".css", ".json", ".yaml", ".yml", ".mjs", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for index, line in enumerate(text.splitlines(), 1):
            for match in PATTERN.finditer(line):
                form = match.group(0)
                forms[form] += 1
                sites.setdefault(form, []).append(
                    f"{path.relative_to(root)}:{index}"
                )

    for form, count in forms.most_common():
        print()
        print(f"  {form!r}  x{count}")
        for site in sites[form][:6]:
            print(f"      {site}")
        if len(sites[form]) > 6:
            print(f"      ... and {len(sites[form]) - 6} more")
    print()
