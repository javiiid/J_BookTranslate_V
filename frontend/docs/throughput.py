"""What the database says about real throughput and cost."""
import sys

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.storage.database import db  # noqa: E402

print(f"{'job':14} {'done/total':>12} {'tok_in':>8} {'tok_out':>8} {'retries':>8} {'cost':>6}")
print("-" * 62)
for row in db.fetch_all(
    "SELECT id, progress_completed, progress_total, input_tokens, output_tokens, "
    "estimated_cost, retry_count FROM jobs ORDER BY id"
):
    done = row["progress_completed"] or 0
    total = row["progress_total"] or 0
    print(f"{row['id']:14} {f'{done}/{total}':>12} {row['input_tokens'] or 0:>8} "
          f"{row['output_tokens'] or 0:>8} {row['retry_count'] or 0:>8} "
          f"{row['estimated_cost'] or 0:>6}")

print()
print("Note: token and cost columns are never written by the pipeline")
print("(confirmed during the audit), so they read 0 regardless of real usage.")
print()
print("=== glossary cost multiplier ===")
print("  auto_glossary ON  -> +1 LLM call per chunk (learn_chunk, max_tokens=2000)")
print("  auto_glossary OFF -> no extra call")
print("  default in the web form: CHECKED -> every default web job pays it")
