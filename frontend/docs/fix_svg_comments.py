"""Replace `--` inside XML comments.

`--` is illegal inside an XML comment, and the SVGs are parsed as XML both by
the test and by the browser. PowerShell regex made a mess of the em-dashes in
the prose, so the comments are rewritten line by line in Python where the
substitution is explicit and reportable.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

TARGETS = [
    Path(r"D:\J_BookTranslate_V\frontend\ui\public\brand\kalima-mark-light.svg"),
    Path(r"D:\J_BookTranslate_V\frontend\ui\public\brand\kalima-mark-dark.svg"),
    Path(r"D:\J_BookTranslate_V\frontend\ui\public\favicon.svg"),
]

for path in TARGETS:
    text = path.read_text(encoding="utf-8")

    def fix(match: re.Match) -> str:
        body = match.group(1)
        # Inside a comment: `--` is illegal, so it becomes a single hyphen.
        return "<!--" + body.replace("--", "-") + "-->"

    fixed = re.sub(r"<!--(.*?)-->", fix, text, flags=re.S)

    if fixed != text:
        path.write_text(fixed, encoding="utf-8", newline="\n")
        print(f"  {path.name}: comments rewritten")

    # Report anything left, wherever it is.
    for index, line in enumerate(fixed.splitlines(), 1):
        if "--" in line.replace("<!--", "").replace("-->", ""):
            print(f"  STILL PRESENT {path.name}:{index}  {line.strip()[:80]}")

    # Prove it parses.
    import xml.etree.ElementTree as ET
    try:
        ET.parse(path)
        print(f"  {path.name}: parses as XML")
    except ET.ParseError as error:
        print(f"  {path.name}: PARSE ERROR {error}")
