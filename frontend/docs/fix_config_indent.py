"""Fix the indentation of the chunking block in config.yaml.

The keys under ``translation:`` are indented two spaces, and the block was
inserted with four, so YAML read line 58 as a nested mapping and refused the
file. Comments are not indentation-sensitive, so only the key lines and their
blank separators need to move.

Verified by parsing the result, because a config file that does not parse takes
the whole engine down and no unit test in the suite reads it.
"""
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")

PATH = Path(r"D:\J_BookTranslate_V\config\config.yaml")
lines = PATH.read_text(encoding="utf-8").splitlines(keepends=True)

KEYS = (
    "semantic_chunking:",
    "chunk_max_tokens:",
    "chunk_context_window:",
    "chunk_min_tokens:",
)

# The block runs from the first chunking comment to the last inserted key.
start = next(i for i, line in enumerate(lines) if "--- chunking" in line)
end = max(i for i, line in enumerate(lines) if line.strip().startswith(KEYS))

changed = []
for i in range(start, end + 1):
    line = lines[i]
    stripped = line.strip()
    if not stripped:
        continue
    if not line.startswith("    "):
        continue
    lines[i] = line[2:]
    changed.append(i + 1)

PATH.write_text("".join(lines), encoding="utf-8")
print(f"  de-indented {len(changed)} line(s): {changed}")

# Parse it. This is the only assertion that matters.
data = yaml.safe_load(PATH.read_text(encoding="utf-8"))
translation = data["translation"]
print(f"  translation keys: {sorted(translation)}")
for key in ("semantic_chunking", "chunk_max_tokens", "chunk_context_window", "chunk_min_tokens"):
    if key not in translation:
        print(f"  MISSING {key}")
        raise SystemExit(1)
    print(f"    {key} = {translation[key]!r}")

# And the values the engine will actually read.
sys.path.insert(0, str(PATH.parent.parent))
from app.core.config import get_chunking_config  # noqa: E402

print(f"  get_chunking_config() -> {get_chunking_config()}")
