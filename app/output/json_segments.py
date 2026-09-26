# ============================================================
# app/output/json_segments.py
# ============================================================
"""
OUTPUT: JSON_SEGMENTS

Machine-readable segment pairs designed for Translation Memory
import. Every translated chunk becomes a corpus entry:

    {
      "segments": [
        {
          "id": "chunk-0",
          "source": "...",
          "target": "...",
          "format": "epub",
          "chapter": "chapter-1.xhtml",
          "flagged": false,
          "notes": []
        }
      ]
    }

Flagged segments (``{NOTE:}``/``{BOUNDARY_WARNING}``) carry
``flagged`` set to True and are safe to exclude from TM imports.
"""

from __future__ import annotations

import json
from pathlib import Path


def segments_as_dict(
    segments,
    title="",
    to_lang="",
):
    """
    Convert segment records to a TM-ready JSON document.
    """

    return {
        "book": title,
        "to_language": to_lang,
        "segments": [
            {
                "id": segment["id"],
                "source": segment["source"],
                "target": segment["target"],
                "format": segment["format"],
                "chapter": segment["chapter"],
                "flagged": bool(segment["flagged"]),
                "notes": list(segment.get("notes", [])),
                **({"quality": segment["quality"]} if segment.get("quality") else {}),
            }
            for segment in (segments or [])
        ],
    }


def write_json_segments(
    segments,
    path,
    title="",
    to_lang="",
):
    """
    Write the JSON_SEGMENTS output file.
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = segments_as_dict(
        segments,
        title=title,
        to_lang=to_lang,
    )

    path.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path