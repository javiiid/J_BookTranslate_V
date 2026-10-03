"""Regression tests for the cross-origin write guard.

The threat: a local HTTP server with no Origin check can be driven by any web
page the user visits. A cross-origin POST with `Content-Type: text/plain` is a
CORS "simple request" - the browser sends it with no preflight, so CORS cannot
stop it - and the handler would then spend the user's provider credits.
"""
import sys
from pathlib import Path

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.web import _loopback_authority, _origin_permitted  # noqa: E402

print("=== origin allowlist ===")
cases = [
    ("http://127.0.0.1:8765", True, "the app's own origin"),
    ("http://localhost:8765", True, "the app via localhost"),
    ("http://localhost:5173", True, "Vite dev proxy"),
    ("http://127.0.0.1:3000", True, "another local dev tool"),
    ("https://attacker.example", False, "remote site"),
    ("http://attacker.example", False, "remote site, http"),
    ("null", False, "sandboxed iframe / file origin"),
    ("http://127.0.0.1.evil.com", False, "suffix lookalike"),
    ("http://localhost.evil.com", False, "suffix lookalike"),
    ("http://127.0.0.1:8765.evil.com", False, "port lookalike"),
    ("file://", False, "local file"),
    ("", False, "empty"),
]
failures = 0
for origin, expected, why in cases:
    allowed = _origin_permitted(origin)
    ok = allowed is expected
    failures += not ok
    print(f"  {'ok ' if ok else 'FAIL'} {origin:32} -> {'ALLOW' if allowed else 'block':6} ({why})")

print()
print("=== host authority (DNS rebinding) ===")
host_cases = [
    ("127.0.0.1:8765", True),
    ("localhost:8765", True),
    ("127.0.0.1", True),
    ("localhost", True),
    ("attacker.example", False),
    ("127.0.0.1.attacker.example", False),
    ("192.168.1.5:8765", False),
    ("[::1]:8765", False),
]
for host, expected in host_cases:
    allowed = _loopback_authority(host)
    ok = allowed is expected
    failures += not ok
    print(f"  {'ok ' if ok else 'FAIL'} {host:32} -> {'ALLOW' if allowed else 'block'}")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
