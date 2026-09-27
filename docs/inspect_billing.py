"""Inspect pending billing rows so we do not delete the user's own data."""
import sys

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.storage.database import db  # noqa: E402

rows = db.fetch_all(
    "SELECT id, kind, reference_id, amount_usd, status, created_at "
    "FROM billing_transactions ORDER BY id"
)
print(f"{len(rows)} billing rows total\n")
for row in rows:
    print(f"  #{row['id']:<4} {row['kind']:<10} {str(row['reference_id']):<12} "
          f"${row['amount_usd']:<7} {row['status']:<10} {row['created_at']}")

print()
# The audit tests only ever attempted kind='credits' reference_id='creator'.
mine = [r for r in rows if r["kind"] == "credits" and r["reference_id"] == "creator"
        and r["amount_usd"] == 20.0]
print(f"rows that look like the audit probe (credits/creator/$20): {len(mine)}")
