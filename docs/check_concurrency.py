"""Verify the concurrency ceiling is applied consistently everywhere."""
import sys

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import (  # noqa: E402
    MAX_TRANSLATION_CONCURRENCY,
    get_translation_config,
    read_config_safe,
)
from app.translation.translator import (  # noqa: E402
    _build_rate_limiter,
    _glossary_mode,
    _translation_concurrency,
)

failures = 0

print("=== what config.yaml actually says ===")
print("-" * 62)
config = get_translation_config()
print(f"  max_concurrency     : {config.get('max_concurrency')}")
print(f"  glossary_mode       : {config.get('glossary_mode')}")
print(f"  requests_per_minute : {config.get('requests_per_minute')}")

print()
print("=== what the engine resolves ===")
print("-" * 62)
workers = _translation_concurrency()
mode = _glossary_mode()
limiter = _build_rate_limiter(workers)
print(f"  _translation_concurrency() -> {workers}")
print(f"  _glossary_mode()            -> {mode}")
print(f"  _build_rate_limiter()       -> "
      f"{'active, ' + str(limiter.current_rpm) + ' rpm' if limiter else 'DISABLED (no rpm set)'}")

print()
print("=== consistency of the ceiling ===")
print("-" * 62)
print(f"  MAX_TRANSLATION_CONCURRENCY = {MAX_TRANSLATION_CONCURRENCY}")
ok = workers == MAX_TRANSLATION_CONCURRENCY
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} engine uses the full ceiling")

ok = config.get("max_concurrency") == MAX_TRANSLATION_CONCURRENCY
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} config.yaml requests the full ceiling")

ok = mode == "deferred"
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} glossary_mode is deferred (fast)")

ok = limiter is not None
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} rate limiter is armed")

if limiter:
    ok = limiter.current_rpm == config.get("requests_per_minute")
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} limiter ceiling matches config "
          f"({limiter.current_rpm} rpm)")

# The web API must reject anything above the shared constant.
import app.web as web  # noqa: E402
ok = web.MAX_TRANSLATION_CONCURRENCY == MAX_TRANSLATION_CONCURRENCY
failures += not ok
print(f"  {'ok  ' if ok else 'FAIL'} web.py validates against the same constant")

# A value above the ceiling must be clamped, not honoured.
saved = config.get("max_concurrency")
try:
    write_probe = read_config_safe()
    write_probe["translation"]["max_concurrency"] = 999
    from app.core.config import write_config  # noqa: E402
    write_config(write_probe)
    clamped = _translation_concurrency()
    ok = clamped == MAX_TRANSLATION_CONCURRENCY
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} an absurd 999 is clamped to {clamped}")
finally:
    restore = read_config_safe()
    restore["translation"]["max_concurrency"] = saved
    write_config(restore)

print()
print("=== restored config ===")
final = get_translation_config()
print(f"  max_concurrency: {final.get('max_concurrency')}  "
      f"glossary_mode: {final.get('glossary_mode')}  "
      f"rpm: {final.get('requests_per_minute')}")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
