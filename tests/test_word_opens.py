"""Word has to be able to open the file.

## What this is for

Every other test in this suite reads the package and asserts things about its
contents. All 587 of them passed while Word refused to open the output with
"The file appears to be corrupted." Asserting on the XML cannot catch that,
because nothing in the XML is malformed: the parts are all well-formed, the
relationships all resolve, and every element is in the right order. Word
validates against its own idea of the OPC profile and refuses the *package*.

So this file does two things. The static tests pin the three values Word checks
that the rest of the suite had wrong, so the same mistake cannot come back
unnoticed on a machine with no Word. The live test opens the document in Word
itself and is skipped when Word is not installed.

## The three values

``docProps/core.xml`` timestamps are ``W3CDTF``, which Word accepts only as
seconds and a ``Z``. The code wrote ``datetime.isoformat()``, which emits
microseconds and a ``+00:00`` offset.

``w:fontKey`` is an ``ST_Guid``, whose pattern is the canonical GUID form --
braces *and* dashes. It was written as 32 bare hex digits, on the reasoning that
the dashes were a mistake. Word validates the pattern and rejects the document.

``CT_Font`` has exactly four embedded-font children. The table used
``embedMedium``, ``embedSemiBold`` and ``embedBlack``, which do not exist.

The last two were introduced by an earlier fix in this same file's history, each
with a comment explaining why the change was correct. That is what this file is
for.
"""
from __future__ import annotations

import re
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

sys.stdout.reconfigure(encoding="utf-8")

from app.output.docx import write_docx
from app.output.rtl_docx import EMBEDDED_FACES, fix_docx_typography

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CP = "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}"
DCTERMS = "{http://purl.org/dc/terms/}"

#: ECMA-376 17.8.1. `CT_Font` has these four embedded-font children and no others.
LEGAL_EMBED_SLOTS = frozenset({"embedRegular", "embedBold", "embedItalic", "embedBoldItalic"})

#: `ST_Guid`, verbatim from the schema: braces, then 8-4-4-4-12 in upper case.
ST_GUID = re.compile(r"\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}")

TITLES = [
    "تاریکی برمی‌خیزد",
    "گرین‌ویچ",
    "شاه خاکستری",
    "نقره بر درخت",
    "بوگارت",
    "بوگارت و هیولا",
    "پسر سبز",
    "شاه سایه‌ها",
    "پسر جادوگر",
]


def segments(titles: list[str] | None = None) -> list[dict]:
    return [
        {
            "id": f"chunk-{index}",
            "position": index,
            "source": title,
            "target": title,
            "format": "epub",
            "chapter": "ch00",
            "flagged": False,
            "notes": [],
        }
        for index, title in enumerate(titles if titles is not None else TITLES)
    ]


def build(target: Path, titles: list[str] | None = None, to_lang: str = "FA",
          title: str = "فهرست") -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    write_docx(segments(titles), str(target), title=title, to_lang=to_lang)
    fix_docx_typography(target)
    return target


def part(target: Path, name: str) -> ElementTree.Element:
    with zipfile.ZipFile(target) as archive:
        return ElementTree.fromstring(archive.read(name))


class TestTheCorePropertiesPart:
    """The first of the two things Word rejected."""

    @pytest.fixture(scope="class")
    @classmethod
    def docx(cls, tmp_path_factory):
        return build(tmp_path_factory.mktemp("core") / "a.docx")

    @pytest.fixture(scope="class")
    @classmethod
    def core(cls, docx):
        return part(docx, "docProps/core.xml")

    def test_every_timestamp_is_w3cdtf(self, core):
        """Seconds and a ``Z``, or Word refuses the document.

        ``datetime.isoformat()`` writes microseconds and a numeric offset, which
        is a legal ``xsd:dateTime`` but not the ``W3CDTF`` profile Word's OPC
        reader enforces.
        """
        stamps = [
            element.text
            for element in core.iter()
            if element.tag in {f"{DCTERMS}created", f"{DCTERMS}modified"}
        ]
        assert stamps, "the part carries no timestamps at all"
        for text in stamps:
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text), text

    def test_the_part_declares_utf8(self, docx):
        with zipfile.ZipFile(docx) as archive:
            markup = archive.read("docProps/core.xml").decode("utf-8")
        assert 'encoding="UTF-8"' in markup.split("?>")[0]


class TestTheFontTable:
    """The second of the two."""

    @pytest.fixture(scope="class")
    @classmethod
    def fonts(cls, tmp_path_factory):
        return part(build(tmp_path_factory.mktemp("fonts") / "a.docx"),
                    "word/fontTable.xml")

    def test_no_embed_slot_outside_the_schema(self, fonts):
        for font in fonts.iter(f"{W}font"):
            for child in font:
                name = child.tag.replace(W, "")
                if name.startswith("embed"):
                    assert name in LEGAL_EMBED_SLOTS, (font.get(f"{W}name"), name)

    def test_every_font_key_is_a_canonical_guid(self, fonts):
        found = 0
        for font in fonts.iter(f"{W}font"):
            for child in font:
                if not child.tag.replace(W, "").startswith("embed"):
                    continue
                found += 1
                key = child.get(f"{W}fontKey")
                assert ST_GUID.fullmatch(key or ""), key
                # And it has to be a real GUID, not 32 hex digits in a costume.
                uuid.UUID(key.strip("{}"))
        assert found, "no embedded font at all"

    def test_the_children_are_in_the_order_the_schema_declares(self, fonts):
        order = ("altName", "panose1", "charset", "family", "notTrueType", "pitch",
                 "sig", "embedRegular", "embedBold", "embedItalic", "embedBoldItalic")
        ranks = {f"{W}{name}": index for index, name in enumerate(order)}
        for font in fonts.iter(f"{W}font"):
            seen = [ranks.get(child.tag, len(ranks)) for child in font]
            assert seen == sorted(seen), [c.tag.replace(W, "") for c in font]

    def test_every_face_is_carried(self, fonts):
        names = {font.get(f"{W}name") for font in fonts.iter(f"{W}font")}
        for _weight, _slot, family in EMBEDDED_FACES:
            assert family in names, family


# ---------------------------------------------------------------------------
# The live check. This is the only assertion here that consults Word.
# ---------------------------------------------------------------------------

WORD = Path("C:/Program Files/Microsoft Office/root/Office16/WINWORD.EXE")
OPEN_SCRIPT = Path(__file__).parent.parent / "scripts" / "word_open.ps1"


def word_available() -> bool:
    if not (WORD.exists() and OPEN_SCRIPT.exists()):
        return False
    probe = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "try { $w = New-Object -ComObject Word.Application; $w.Quit() } catch { exit 1 }"],
        capture_output=True, timeout=120,
    )
    return probe.returncode == 0


requires_word = pytest.mark.skipif(
    not word_available(),
    reason="Word is not available, so the only assertion that can catch this cannot run",
)


class TestWordActuallyOpensIt:
    """The assertion the rest of the suite was unable to make."""

    def test_word_opens_a_persian_book(self, tmp_path):
        target = build(tmp_path / "persian.docx")
        result = _open_in_word(target)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "corrupt" not in (result.stdout + result.stderr).lower()
        paragraphs = _paragraph_count(result.stdout)
        assert paragraphs >= len(TITLES), result.stdout

    def test_word_opens_an_english_book(self, tmp_path):
        target = build(tmp_path / "english.docx", titles=["A Plain English Title"],
                       to_lang="EN", title="Book")
        result = _open_in_word(target)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_word_reads_the_titles_back_in_order(self, tmp_path):
        """Not just "it opened" -- the text survives the round trip intact."""
        target = build(tmp_path / "readback.docx")
        text_path = target.with_suffix(".txt")
        result = _open_in_word(target, text_out=text_path)
        assert result.returncode == 0, result.stdout + result.stderr
        laid_out = text_path.read_text(encoding="utf-8")
        for title in TITLES:
            assert title in laid_out, title


def _open_in_word(target: Path, text_out: Path | None = None) -> subprocess.CompletedProcess:
    """Open in a *fresh* Word process, and always reap it.

    A shared instance is not usable for this: after one refusal it will not open
    anything else either, so a second failure tells you nothing about the second
    file. And `Quit()` alone leaves WINWORD processes behind, which then contend
    and make the results meaningless.
    """
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(OPEN_SCRIPT), "-Path", str(target.resolve())]
    if text_out is not None:
        command += ["-TextOut", str(text_out.resolve())]
    return subprocess.run(command, capture_output=True, text=True, timeout=300)


def _paragraph_count(stdout: str) -> int:
    match = re.search(r"paragraphs=(\d+)", stdout)
    return int(match.group(1)) if match else 0
