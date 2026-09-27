"""Remove the probe rows created while verifying the CSRF finding.

The verification inserted real rows into the user's database. Leaving them would
pollute the account portal with fake keys, a fake business request, and a fake
billing transaction. Only rows created by this probe are touched.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, r"D:\J_BookTranslate_V")
from app.storage.database import db  # noqa: E402

PROBE_KEYS = ("probe-json", "probe-textplain")

removed = {}

for name in PROBE_KEYS:
    removed[f"api_key:{name}"] = db.execute("DELETE FROM account_api_keys WHERE name=?", (name,))

removed["business_request"] = db.execute(
    "DELETE FROM business_requests WHERE contact_name=?", ("x",)
)
removed["billing_transaction"] = db.execute(
    "DELETE FROM billing_transactions WHERE reference_id=? AND status='pending' AND amount_usd=35.0",
    ("creator",),
)

print("cleanup result (rows deleted):")
for key, count in removed.items():
    print(f"  {key:32} {count}")

print()
print("remaining probe keys:",
      db.fetch_one("SELECT COUNT(*) AS n FROM account_api_keys WHERE name LIKE 'probe-%'")["n"])
print("pending 35.0 transactions:",
      db.fetch_one("SELECT COUNT(*) AS n FROM billing_transactions WHERE amount_usd=35.0 AND status='pending'")["n"])
print("total api keys now:", db.fetch_one("SELECT COUNT(*) AS n FROM account_api_keys")["n"])
