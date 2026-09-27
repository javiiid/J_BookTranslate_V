"""Build an accurate untested-module map.

A naive "does the dotted path appear in the test sources" check produces false
positives because the suite imports both ways:

    from app.output import docx as docx_module     # not "app.output.docx"
    from app.reader.service import chapter          # is "app.reader.service"

Both forms have to be recognised before claiming a module is untested.
"""
import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\J_BookTranslate_V")
TESTS = ROOT / "tests"
APP = ROOT / "app"


def module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


# Collect every symbol the suite touches, in both import styles.
dotted: set[str] = set()
symbols: dict[str, set[str]] = {}  # package -> {symbol}

for test_file in sorted(TESTS.glob("*.py")):
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
            dotted.add(node.module)
            symbols.setdefault(node.module, set()).update(
                alias.name for alias in node.names
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app"):
                    dotted.add(alias.name)


def covered(module: str) -> bool:
    if module in dotted:
        return True
    # `from app.output import docx` covers the module app.output.docx
    if "." in module:
        package, _, name = module.rpartition(".")
        if name in symbols.get(package, set()):
            return True
    return False


modules = [p for p in sorted(APP.rglob("*.py")) if p.name != "__init__.py"]
untested = []
total_untested = 0

print(f"{'module':44} {'lines':>6}  status")
print("-" * 66)
for path in modules:
    mod = module_name(path)
    lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    if covered(mod):
        status = "tested"
    else:
        status = "UNTESTED"
        untested.append((mod, lines))
        total_untested += lines
    print(f"{mod:44} {lines:>6}  {status}")

print("-" * 66)
print(f"untested modules: {len(untested)} of {len(modules)}")
print(f"untested lines  : {total_untested}")
print()
for mod, lines in sorted(untested, key=lambda x: -x[1])[:12]:
    print(f"  {mod:42} {lines:>5}")
