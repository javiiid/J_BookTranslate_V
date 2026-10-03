"""Recount the tree properly.

The earlier counts used PowerShell `Measure-Object -Line`, which does not count
empty lines, so every number was too low. This uses splitlines() so the README
table matches what a reader would get from a line count.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\J_BookTranslate_V")


def count(files):
    return sum(len(p.read_text(encoding="utf-8", errors="ignore").splitlines()) for p in files)


print("=== app packages ===")
print(f"  {'package':14} {'files':>5} {'lines':>10}")
app_total_lines = 0
app_total_files = 0
rows = []
for package in sorted(p for p in (ROOT / "app").iterdir()
                      if p.is_dir() and p.name != "__pycache__"):
    files = [p for p in package.rglob("*.py") if "__pycache__" not in str(p)]
    if not files:
        continue
    lines = count(files)
    rows.append((package.name, len(files), lines))
    app_total_lines += lines
    app_total_files += len(files)
    print(f"  {package.name:14} {len(files):>5} {lines:>10}")

print()
print("=== top-level modules ===")
root_lines = 0
for module in sorted((ROOT / "app").glob("*.py")):
    lines = len(module.read_text(encoding="utf-8", errors="ignore").splitlines())
    root_lines += lines
    print(f"  {module.name:20} {lines:>10}")

print()
print("=== tests ===")
test_files = [p for p in (ROOT / "tests").rglob("*.py") if "__pycache__" not in str(p)]
test_lines = count(test_files)
print(f"  {len(test_files):>5} files {test_lines:>10}")

print()
print("=== totals ===")
total_lines = app_total_lines + root_lines + test_lines
print(f"  app/ (packages)   {app_total_lines:>10}")
print(f"  app/ (top level)  {root_lines:>10}")
print(f"  tests/            {test_lines:>10}")
print("  ---")
print(f"  everything        {total_lines:>10}")
print(f"  app/ only         {app_total_lines + root_lines:>10}")
