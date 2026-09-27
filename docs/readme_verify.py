"""Pin down the facts the README must not get wrong.

Two claims in the current README are checked here against the code rather than
trusted: the port the server binds, and whether `--mode pdfbilingual` actually
works. The CLI advertises that mode, and the README tells users to run it.
"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

import app.web as web  # noqa: E402
from app.translation.translator import process_translations  # noqa: E402

print("=== the port ===")
source = inspect.getsource(web)
import re  # noqa: E402
for pattern in (r"\b(\d{4,5})\b(?=[^\n]*serve_forever)",
                r"HTTPServer\([^)]*?(\d{4,5})",
                r"['\"]:?(\d{4,5})['\"]"):
    for match in re.finditer(pattern, source, re.S):
        line = source[: match.start()].count("\n") + 1
        print(f"  line {line}: {match.group(1)}")
        break

print()
print("=== does --mode pdfbilingual work end to end? ===")
signature = inspect.signature(process_translations)
print(f"  process_translations mode default: {signature.parameters['mode'].default!r}")

body = inspect.getsource(process_translations)
whitelist = re.search(r"supported_modes\s*=\s*\{(.*?)\}", body, re.S)
modes = re.findall(r'"([^"]+)"', whitelist.group(1)) if whitelist else []
print(f"  modes it will accept : {modes}")
print(f"  modes the CLI offers : ['batch', 'resume', 'test', 'batchcheck', 'resumebatch', 'pdfbilingual']")

missing = [m for m in ["batch", "resume", "test", "batchcheck", "resumebatch", "pdfbilingual"]
           if m not in modes]
print(f"  offered but rejected : {missing}")

# Prove it rather than infer: call it and see the error.
probe = dict(
    client=None, chunks=[], from_lang="EN", to_lang="FA", mode="pdfbilingual",
)
try:
    process_translations(**probe)
    print("  pdfbilingual: accepted (no error)")
except ValueError as error:
    print(f"  pdfbilingual: ValueError -> {error}")
except TypeError as error:
    print(f"  pdfbilingual: TypeError -> {error}")
except Exception as error:  # noqa: BLE001
    print(f"  pdfbilingual: {type(error).__name__} -> {error}")

print()
print("=== the output formats the CLI can actually write ===")
from app.output.formats import available_output_formats  # noqa: E402

try:
    names = available_output_formats()
    print(f"  available_output_formats() -> {len(names)} format(s)")
    for name in names:
        print(f"    {name}")
except Exception as error:  # noqa: BLE001
    print(f"  could not call it: {type(error).__name__}: {error}")
