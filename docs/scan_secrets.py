"""Scan everything about to be committed for secrets.

A blanket `*.yaml` gitignore is what currently keeps the API key out of the
repo. That is one rule between a live key and a public GitHub page, so this
checks the actual staged content rather than trusting the ignore rules, and
also reports which files the rules are hiding in case one of them matters.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# This script lives in a *different* repo (J_Translate_Ui/docs). Without this
# every git call below would resolve against that repo and report the wrong
# answer -- including "the live config is excluded", which is the one line
# that must not be wrong.
REPO = Path(r"D:\J_BookTranslate_V")


def git(*args):
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=False,
    )

PATTERNS = [
    (r"sk-[A-Za-z0-9]{16,}", "OpenAI-style API key"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub personal access token"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub fine-grained token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"AIza[0-9A-Za-z_\-]{30,}", "Google API key"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
    (r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*['\"][^'\"\s]{8,}",
     "assigned credential"),
]

PLACEHOLDERS = re.compile(
    r"(?i)(your[-_ ]|example|dummy|placeholder|xxx+|changeme|<your|redacted|fake|"
    r"test[-_]key|not[-_]a[-_]real|sk-t2zl)"
)

# Anything git would actually publish.
staged = git("diff", "--cached", "--name-only", "--diff-filter=ACMR").stdout.split()

untracked = [
    line[3:] for line in git("status", "--porcelain").stdout.splitlines()
    if line.startswith("??")
]

candidates = sorted({p for p in staged + untracked if p})
print(f"=== repo: {REPO} ===")
print(f"=== scanning {len(candidates)} path(s) git would publish ===\n")

findings = []
for path in candidates:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
    except (OSError, IsADirectoryError):
        continue
    for pattern, label in PATTERNS:
        for match in re.finditer(pattern, text):
            line = text[:match.start()].count("\n") + 1
            snippet = match.group(0)
            if PLACEHOLDERS.search(snippet):
                print(f"  skip  {path}:{line}  {label} (looks like a placeholder)")
                continue
            findings.append((path, line, label, snippet[:70]))

if findings:
    print("SECRETS FOUND -- do not commit:\n")
    for path, line, label, snippet in findings:
        print(f"  {path}:{line}  {label}\n      {snippet}")
else:
    print("  no secrets found in the files git would publish\n")

print("=== is the live config actually excluded? ===")
for probe in ("config/config.yaml", "config/config.local.yaml"):
    ignored = git("check-ignore", "-q", probe).returncode == 0
    tracked = git("ls-files", "--error-unmatch", probe).returncode == 0
    if tracked:
        print(f"  DANGER  {probe} is TRACKED and would publish the key")
    elif ignored:
        print(f"  ok      {probe} ignored and untracked")
    else:
        print(f"  WARNING {probe} is neither ignored nor tracked")

print()
print("VERDICT:", "BLOCKED" if findings else "CLEAR")
sys.exit(1 if findings else 0)
