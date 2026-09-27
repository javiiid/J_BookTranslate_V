"""Check every factual claim the new README makes.

A README is the one file users trust without verifying, so each number and
path in it is checked against the code here rather than assumed. Anything that
cannot be confirmed is reported so it can be corrected before publishing.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\J_BookTranslate_V")
README = (ROOT / "readme.md").read_text(encoding="utf-8")

failures = []


def check(label, condition, detail=""):
    if not condition:
        failures.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))


print("=== numbers quoted in the README ===")
print("-" * 72)

sys.path.insert(0, str(ROOT))

# Persian digits are Unicode decimal digits, so \d matches them -- but
# `(\d+)\s+تست` also matched "3.14 تست شده" in the prerequisites section and
# reported 14. Anchor on the specific phrases instead.
def persian_to_int(text):
    # U+066C is the Arabic thousands separator and appears throughout the
    # Persian text; strip grouping marks before converting the digits.
    cleaned = text.replace("٬", "").replace(",", "")
    return int(cleaned.translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))


result = subprocess.run(
    [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q",
     "-p", "no:cacheprovider", "--basetemp", str(ROOT / ".test-tmp" / "readme")],
    capture_output=True, text=True, cwd=ROOT, check=False,
)
matched = re.search(r"(\d+) passed", result.stdout)
actual_tests = int(matched.group(1)) if matched else 0
claimed = re.search(r"\*\*([۰-۹0-9]+)\s+تست", README)
claimed_tests = persian_to_int(claimed.group(1)) if claimed else 0
check(f"test count: README says {claimed_tests}, suite says {actual_tests}",
      claimed_tests == actual_tests)
check("the badge agrees", f"tests-{actual_tests}%20passing" in README)


def count(files):
    return sum(len(p.read_text(encoding="utf-8", errors="ignore").splitlines()) for p in files)


app_files = [p for p in (ROOT / "app").rglob("*.py") if "__pycache__" not in str(p)]
test_files = [p for p in (ROOT / "tests").rglob("*.py") if "__pycache__" not in str(p)]
app_loc = count(app_files)
claimed_loc = persian_to_int(re.search(r"\*\*([۰-۹,٬]+)\s+خط پایتون", README).group(1)
                             .replace("٬", "").replace(",", ""))
check(f"app line count: README says {claimed_loc:,}, tree has {app_loc:,}",
      claimed_loc == app_loc, f"{app_loc:,} actual")
grand_total = app_loc + count(test_files)


def to_persian(number):
    return f"{number:,}".replace(",", "٬").translate(
        str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


check("the with-tests total is also stated", to_persian(grand_total) in README,
      f"app {to_persian(app_loc)} + tests {to_persian(count(test_files))}"
      f" = {to_persian(grand_total)}")

deps = [line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines() if line.strip()]
check(f"dependency count: README says 3, requirements has {len(deps)}",
      len(deps) == 3, str(deps))

print()
print("=== the benchmark table ===")
print("-" * 72)
for claim in ["۷۲.۲ ثانیه", "۲۴.۲ ثانیه", "۱۲.۳ ثانیه", "۶.۶ ثانیه",
              "۱۰.۹۰×", "۲.۹۹×", "۵.۸۶×"]:
    check(f"quotes {claim}", claim in README)

print()
print("=== packages and their line counts ===")
print("-" * 72)
# Each tree row ends with "(N files,  M lines)" in Persian digits.
ROW = re.compile(r"([a-z_]+)/[^\n]*?([۰-۹]+)\s*فایل،?\s*([۰-۹٬,]+)\s*خط")
rows = ROW.findall(README)
check("the tree table has rows to check", len(rows) >= 10, f"{len(rows)} rows found")
for name, files, lines in rows:
    # tests/ is a tree root, not a package under app/.
    package = ROOT / ("app" if name != "tests" else "") / name
    if not package.is_dir():
        check(f"{name}/ exists", False, "directory not found")
        continue
    actual_files = [p for p in package.rglob("*.py") if "__pycache__" not in str(p)]
    actual = count(actual_files)
    check(f"{name}/: README says {persian_to_int(files)} files / {persian_to_int(lines)} lines,"
          f" actual {len(actual_files)} / {actual}",
          persian_to_int(files) == len(actual_files) and persian_to_int(lines) == actual)

print()
print("=== config keys: every one must exist in the real file ===")
print("-" * 72)
config = (ROOT / "config" / "config.yaml").read_text(encoding="utf-8")
for key in re.findall(r"`translation\.([a-z_]+)`", README) + re.findall(r"`openai\.([a-z_]+)`", README):
    check(f"config.yaml has {key}", re.search(rf"^\s*{key}:", config, re.M) is not None)

print()
print("=== routes and modes ===")
print("-" * 72)
for route in ["/landing", "/workspace", "/library", "/account", "/reader/", "/workspace/job/"]:
    check(f"route {route} is served", route in (ROOT / "app" / "web.py").read_text(encoding="utf-8"))
check("port 8765 is the real one", "8765" in (ROOT / "app" / "web.py").read_text(encoding="utf-8"))

from app.output.formats import available_output_formats  # noqa: E402

formats = set(available_output_formats())
claimed = set(re.findall(r"\| `([a-z_]+)` \|", README))
for name in sorted(formats):
    check(f"output format {name} is listed in the README", name in claimed)
extra = {n for n in claimed if n not in formats} - {"fast", "off", "deferred", "inline"}
check("the README lists no format that does not exist", not extra, str(sorted(extra)))

print()
print("=== the two honest warnings must be present ===")
print("-" * 72)
check("pdfbilingual is flagged as broken",
      "pdfbilingual" in README and "کار نمی‌کند" in README)
check("the missing LICENSE is stated", "LICENSE" in README and "پروانه" in README)
check("the 93-test claim is called out as wrong", "۹۳ تست" in README)
check("SRT is flagged as unwired", "srt" in README.lower() and "وصل نشده" in README)
check("Ctrl+C tradeoff is disclosed", "۱۲ درخواست پولی" in README)

print()
print("=== the API key must not be in the README ===")
print("-" * 72)
check("no real key", "sk-t2zl" not in README)
check("the placeholder is used instead", "YOUR_API_KEY" in README)

print()
print("=" * 72)
print("FAILURES:", len(failures))
for item in failures:
    print("  -", item)
