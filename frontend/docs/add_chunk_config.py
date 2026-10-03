"""Insert the chunking settings into config.yaml.

Done with a script rather than an edit because the file uses trailing
whitespace on its blank lines, so the text an editor sees and the text on disk are
not the same string. Matching on the setting line and inserting after it avoids
depending on either.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PATH = Path(r"D:\J_BookTranslate_V\config\config.yaml")
lines = PATH.read_text(encoding="utf-8").splitlines(keepends=True)

if any("semantic_chunking" in line for line in lines):
    print("  already present, nothing to do")
    raise SystemExit(0)

anchor = next(
    (i for i, line in enumerate(lines) if line.strip().startswith("glossary_mode")),
    None,
)
if anchor is None:
    print("  could not find glossary_mode to anchor on")
    raise SystemExit(1)

# Match the file's own indentation: two spaces for a key under `translation:`.
block = """
    # --- chunking -------------------------------------------------------
    #
    # The default chunker splits on the literal "</p>", which means it only sees
    # paragraphs written with <p>, counts characters rather than tokens, and does
    # not reproduce the document when reassembled. The semantic chunker in
    # app/pipeline/semantic_chunker.py fixes all three: it finds blocks by
    # scanning tags, budgets in estimated tokens, guarantees that
    # "".join(chunks) == the original document, and sends the preceding blocks
    # as context so pronouns and recurring names resolve.
    #
    # Off by default, and not out of caution about the new code. Chunks are
    # identified by position (chunk-0, chunk-1, ...) and a saved translation is
    # keyed by that id, so turning this on changes what "chunk-7" *is*.
    # Resuming a job started before the change would keep some translations and
    # redo others, and the finished book would mix two segmentations. Start a new
    # job when you turn it on.
    semantic_chunking: false

    # Budget per chunk, in estimated tokens rather than characters. 10,000
    # characters is roughly 2,500 tokens of English and roughly 8,000 of
    # Persian, so the old limit varied by a factor of three with the language.
    chunk_max_tokens: 1200

    # How many preceding blocks of plain text to send as context. It costs no
    # extra API call -- it rides in the same request -- and the context is never
    # translated or stored. 0 disables it.
    chunk_context_window: 2

    # Below this a chunk is not worth its own request, so neighbouring small
    # blocks are packed together. 0 means never merge: one chunk per block.
    chunk_min_tokens: 200
"""

lines.insert(anchor + 1, block)
PATH.write_text("".join(lines), encoding="utf-8")
print(f"  inserted {len(block.splitlines())} lines after line {anchor + 1}")

# Read the keys back, so a silent write failure cannot pass unnoticed.
check = PATH.read_text(encoding="utf-8")
for key in (
    "semantic_chunking",
    "chunk_max_tokens",
    "chunk_context_window",
    "chunk_min_tokens",
):
    if f"{key}:" not in check:
        print(f"  MISSING {key}")
        raise SystemExit(1)
print("  all four keys present")
