"""Prove the TS and Python normalisers agree, on real Persian text.

The React `key()` and the Python `_key()` must produce identical output, or the
two UIs disagree about whether a term is already in the glossary. Comparing them
in the abstract is not enough: the interesting failures are in characters the
specifications treat differently, so this feeds a list of awkward strings
through both implementations and prints any disagreement.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

UI = Path(r"D:\J_BookTranslate_V\frontend\ui")
PY = Path(r"D:\J_BookTranslate_V")

CASES = [
    "واژه‌نامه",              # ZWNJ, extremely common in Persian
    "می‌رود",                        # ZWNJ
    "نمی‌شود",
    "book",                                  # plain ASCII
    "Ann",                                   # case
    "ANN",
    "ＡＢＣ",                          # full-width, NFKC folds this
    "cafe\u0301",                            # combining acute
    "café",                                  # precomposed
    "soft\u00adhyphen",                      # soft hyphen: Python drops it
    "a\u200bb",                              # zero-width space
    "a\u200db",                              # ZWJ
    "a\u202bb",                              # RLE, a bidi control
    "Dagger Society",
    "dagger society",
    "",
    "   ",
    "۱۲۳",
    "١٢٣",                                  # Arabic-Indic digits
]

# The Python reference, copied from app/glossary/service.py.
def python_key(value):
    import unicodedata
    return unicodedata.normalize("NFKC", value).casefold()


# Run the TypeScript implementation through Node so there is no chance of
# re-implementing it in Python and comparing two copies of the same idea.
#
# The script is written to a file and run as UTF-8. Passing Persian text through
# `node -e` mangled it into mojibake, which produced a column of false
# MISMATCHes that had to be read past to find the real ones.
node_script = UI / "scripts" / "normalisation-probe.mjs"
node_script.parent.mkdir(parents=True, exist_ok=True)
node_script.write_text(
    """// Prints the key() output for the cases in docs/check_normalisation.py.
// Kept as a file so the input survives as UTF-8.
import { key } from '../src/lib/terms.ts'

const CASES = %s
process.stdout.write(JSON.stringify(CASES.map(key)))
"""
    % json.dumps(CASES, ensure_ascii=False),
    encoding="utf-8",
)

result = subprocess.run(
    ["node", "--experimental-strip-types", str(node_script)],
    capture_output=True,
    check=True,
)
ts_keys = json.loads(result.stdout.decode("utf-8"))

failures = 0
print(f"{'input':<26} {'python':<26} {'typescript':<26} {''}")
print("-" * 86)
for original, py, ts in zip(CASES, (python_key(v) for v in CASES), ts_keys):
    agree = py == ts
    failures += not agree
    flag = "ok" if agree else "MISMATCH"
    shown = original.replace("\u00ad", "<SHY>").replace("\u200b", "<ZWSP>") \
        .replace("\u200d", "<ZWJ>").replace("\u202b", "<RLE>") \
        .replace("\u200c", "<ZWNJ>").replace("\u0301", "<COMB>")
    print(f"{shown:<26} {py!r:<26} {ts!r:<26} {flag}")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
