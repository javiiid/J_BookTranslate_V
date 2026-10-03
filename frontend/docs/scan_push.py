"""Scan everything that is about to be published, across all unpushed commits.

The earlier scan looked at staged files only. This one reads the actual diff
from origin/main to HEAD, which is the exact byte stream that becomes public,
and also walks the whole history reachable from HEAD so a key committed long
ago cannot slip through unnoticed.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(r"D:\J_BookTranslate_V")


def git(*args, binary=False):
    result = subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, check=False,
    )
    return result.stdout if binary else result.stdout.decode("utf-8", "replace")


PATTERNS = [
    (r"sk-[A-Za-z0-9]{16,}", "OpenAI-style API key"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub fine-grained token"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub personal access token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"AIza[0-9A-Za-z_\-]{30,}", "Google API key"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
]

# The live key, named explicitly. This is the one string that must never appear.
LIVE_KEY_PREFIX = "sk-t2zl"

findings = []

# 1. Every blob that will exist on origin/main after the push.
print("=== every tracked file at HEAD ===")
tracked = git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
print(f"  {len(tracked)} tracked path(s)")

for path in tracked:
    blob = git("show", f"HEAD:{path}", binary=True)
    if not blob:
        continue
    try:
        text = blob.decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        continue
    for pattern, label in PATTERNS:
        for match in re.finditer(pattern, text):
            findings.append((path, label, match.group(0)[:60]))
    if LIVE_KEY_PREFIX in text:
        findings.append((path, "THE LIVE API KEY", LIVE_KEY_PREFIX + "..."))

# 2. Full history, so a key that was committed and later removed is still caught.
print()
print("=== all history reachable from HEAD ===")
log = git("log", "--format=%H", "HEAD").splitlines()
print(f"  {len(log)} commit(s)")
for commit in log:
    patch = git("show", commit, "--format=", "-p")
    for pattern, label in PATTERNS:
        for match in re.finditer(pattern, patch):
            findings.append((f"commit {commit[:8]}", label, match.group(0)[:60]))

print()
if findings:
    print("SECRETS FOUND -- DO NOT PUSH:")
    for where, label, snippet in sorted(set(findings)):
        print(f"  {where}: {label}\n      {snippet}")
else:
    print("  nothing matching a credential pattern in HEAD or in any commit")
    print(f"  the live key prefix '{LIVE_KEY_PREFIX}' appears in: no tracked file")

print()
print("VERDICT:", "BLOCKED" if findings else "SAFE TO PUSH")
sys.exit(1 if findings else 0)
