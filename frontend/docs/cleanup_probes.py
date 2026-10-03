"""Remove the probe rows the audit tests created in the real database."""
import sys

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.storage.database import db  # noqa: E402

patterns = ("legit-%", "evil-%", "csrf-%", "probe-%")
total = 0
for pattern in patterns:
    total += db.execute("DELETE FROM account_api_keys WHERE name LIKE ?", (pattern,))

print("probe api keys deleted:", total)
print("remaining keys:")
for row in db.fetch_all("SELECT name FROM account_api_keys ORDER BY id"):
    print("  ", row["name"][:30])

print()
print("pending checkout rows:",
      db.fetch_one("SELECT COUNT(*) AS n FROM billing_transactions WHERE status='pending'")["n"])
