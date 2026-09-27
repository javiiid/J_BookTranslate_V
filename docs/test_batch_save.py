"""Regression: a completed batch must not lose its translations.

`save_partial_batch_results` called `save_translations(...)` but the name was
never imported, so the call raised NameError. The surrounding
`except Exception` swallowed it and returned None, while the caller had already
deleted the batch state file - paid-for translations were dropped and the user
was told "No batch state found."

This drives the real function with the real on-disk shapes it expects: a
downloaded batch output JSONL and a batch status file carrying the job paths.
"""
import io
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.translation.batch import save_partial_batch_results  # noqa: E402


def batch_line(chunk_id, text):
    """One line of a downloaded batch output file."""
    return json.dumps({
        "custom_id": chunk_id,
        "response": {
            "error": None,
            "body": {"choices": [{"message": {"content": text}}]},
        },
    })


failures = 0

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    job_dir = root / "job"
    job_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "job_dir": str(job_dir),
        "chunks_file": str(job_dir / "chunks.json"),
        "translations_file": str(job_dir / "translations.json"),
        "state_file": str(job_dir / "job_state.json"),
    }
    (job_dir / "chunks.json").write_text(
        json.dumps({"chunks": [["chunk-0", "Hello"], ["chunk-1", "World"]],
                    "chapter_map": {}}),
        encoding="utf-8",
    )

    state_path = job_dir / "batch_status_x.json"
    state_path.write_text(json.dumps({"paths": paths}), encoding="utf-8")

    output_path = job_dir / "batch_x_output.jsonl"
    output_path.write_text(
        "\n".join([
            batch_line("chunk-0", "سلام"),
            batch_line("chunk-1", "جهان"),
            json.dumps({"custom_id": "chunk-2", "response": {"error": "rate limited"}}),
        ]) + "\n",
        encoding="utf-8",
    )

    print("=== real save_partial_batch_results, real on-disk shapes ===")
    # `status` is the provider SDK's Batch object: it is read via attributes
    # (status.status, status.output_file_id), not as a mapping.
    status = SimpleNamespace(
        status="expired",
        output_file_id="file-abc123",
        request_counts=SimpleNamespace(completed=2, total=3),
    )

    class FakeFiles:
        def content(self, file_id):
            # The SDK returns a binary response object exposing .read()
            assert file_id == "file-abc123"
            return io.BytesIO(output_path.read_bytes())

    result = save_partial_batch_results(
        client=SimpleNamespace(files=FakeFiles()),
        temp_dir=job_dir,
        batch_id="x",
        state_file_path=str(state_path),
        status=status,
    )

    count = len(result) if result else 0
    print(f"  returned {count} translations")

    if count != 2:
        print(f"  FAIL: expected 2 translations, got {count} (NameError path returns 0)")
        failures += 1
    else:
        print("  ok  : both translations recovered, errored chunk skipped")

    translations_file = Path(paths["translations_file"])
    if not translations_file.is_file():
        print("  FAIL: translations.json was never written - the work is lost")
        failures += 1
    else:
        saved = json.loads(translations_file.read_text(encoding="utf-8"))
        print(f"  ok  : translations.json -> {saved}")
        if set(saved) != {"chunk-0", "chunk-1"}:
            print("  FAIL: wrong translation keys")
            failures += 1

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
