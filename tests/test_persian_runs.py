"""Persian that Word draws correctly.

## The complaint

Persian titles came out of the DOCX as characters that are *shaped* but not
readable:

    تاریکی برمی‌خیزد · گرین‌ویچ · شاه خاکستری · نقره بر درخت
    بوگارت · بوگارت و هیولا · پسر سبز · شاه سایه‌ها · پسر جادوگر

Every one reads perfectly in a text editor, so the text is right and the
*rendering* is not.

## The cause

Arabic script is joined: a letter has up to four shapes -- isolated, initial,
medial, final -- chosen from the letters on either side. Word runs that shaping
only for a run it knows is right-to-left, and it knows it from ``w:rtl``.

The runs were written as ``<w:rtl w:val="1"/>``. ECMA-376 allows it -- a boolean's
``w:val`` takes ``1``/``0`` -- and Word itself writes the bare element, but for
``w:rtl`` it reads the explicit form as *off*. So the document said "these runs
are right-to-left, value 1" and Word laid them out as left-to-right English.

Measured on the reported titles, before the fix: 5 explicit ``w:rtl w:val="1"``
and 0 bare.

## Why the text still looked Persian

Because the font was right either way -- ``w:cs`` was set. So the glyphs came
from Vazirmatn and were shaped, just in the wrong base direction, which for a
joined script is enough to make a word unreadable rather than merely odd.

A second, quieter part: ``w:szCs``. A right-to-left run is sized from
``w:szCs`` alone, and it is not inherited from ``w:sz``. The runs declared no
size at all -- the size lived in the style -- so the Persian text was sized by
Word's own default instead of the document's 12pt.

## What these tests hold

The properties Word reads, checked on the parsed tree. Matched with the space
``fix_docx_typography``'s ElementTree pass leaves behind -- it writes
``<w:rtl />`` -- because a tight-form substring test fails on correct output.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

sys.stdout.reconfigure(encoding="utf-8")

from app.output.docx import write_docx
from app.output.rtl_docx import fix_docx_typography

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

#: The reported titles, verbatim. Every one of these was unreadable in Word.
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


def segments_for(titles: list[str], chapter: str = "ch00") -> list[dict]:
    return [
        {
            "id": f"chunk-{index}",
            "position": index,
            "source": title,
            "target": title,
            "format": "epub",
            "chapter": chapter,
            "flagged": False,
            "notes": [],
        }
        for index, title in enumerate(titles)
    ]


def build(
    target: Path,
    titles: list[str] | None = None,
    to_lang: str = "FA",
    title: str = "کتاب",
) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    write_docx(
        segments_for(titles if titles is not None else TITLES),
        str(target),
        title=title,
        to_lang=to_lang,
    )
    fix_docx_typography(target)
    return target


def document(target: Path) -> ElementTree.Element:
    with zipfile.ZipFile(target) as archive:
        return ElementTree.fromstring(archive.read("word/document.xml"))


def raw(target: Path, name: str = "word/document.xml") -> str:
    with zipfile.ZipFile(target) as archive:
        return archive.read(name).decode("utf-8")


def is_rtl(run) -> bool:
    """Whether a run is actually right-to-left, not merely has the element.

    A Latin fragment inside Persian is written ``<w:rtl w:val="0"/>`` -- the
    element is present and the run is explicitly *off*. Looking only for the
    element's presence reports those as Persian, which is the opposite of the
    truth, and it is how the first version of this check failed on correct
    output.
    """
    element = run.find(f"{W}rPr/{W}rtl")
    if element is None:
        return False
    return element.get(f"{W}val") not in {"0", "false", "off"}


def persian_runs(root) -> list[ElementTree.Element]:
    """Every run holding at least one Arabic-script character."""
    found = []
    for run in root.iter(f"{W}r"):
        text = "".join(item.text or "" for item in run.iter(f"{W}t"))
        if any("؀" <= ch <= "ۿ" for ch in text):
            found.append(run)
    return found


class TestTheReportedTitles:
    @pytest.fixture(scope="class")
    @classmethod
    def docx(cls, tmp_path_factory):
        return build(tmp_path_factory.mktemp("titles") / "titles.docx")

    def test_every_title_is_in_the_document(self, docx):
        text = " ".join(item.text or "" for item in document(docx).iter(f"{W}t"))
        for title in TITLES:
            assert title in text, title

    def test_every_persian_run_is_marked_rtl(self, docx):
        runs = persian_runs(document(docx))
        assert len(runs) >= len(TITLES), len(runs)
        for run in runs:
            text = "".join(item.text or "" for item in run.iter(f"{W}t"))
            assert is_rtl(run), (
                f"{text!r} carries no w:rtl, so Word will not shape it as Arabic"
            )

    def test_the_rtl_flag_is_written_the_way_word_honours_it(self, docx):
        """The whole bug.

        ``<w:rtl w:val="1"/>`` is legal and Word reads it as *off*. Word writes
        the bare element, and that is the only form it acts on.
        """
        markup = raw(docx)
        assert not re.search(r'<w:rtl w:val="1"\s*/>', markup), (
            "Word reads an explicit w:val on w:rtl as off, so the run is "
            "laid out left-to-right and the Arabic shaping is not applied"
        )
        # And the bare form is genuinely there, not merely the absence of the bad one.
        assert re.search(r"<w:rtl\s*/>", markup), (
            "no run carries a bare w:rtl either"
        )

    def test_every_persian_run_has_a_complex_script_font(self, docx):
        for run in persian_runs(document(docx)):
            text = "".join(item.text or "" for item in run.iter(f"{W}t"))
            fonts = run.find(f"{W}rPr/{W}rFonts")
            assert fonts is not None, text
            # Word picks the complex-script font for a run marked RTL, so this
            # slot -- not `w:ascii` -- is the one that decides.
            assert fonts.get(f"{W}cs") == "Vazirmatn", (text, fonts.get(f"{W}cs"))

    def test_every_persian_run_has_a_complex_script_size(self, docx):
        # A right-to-left run is sized from w:szCs alone, and it does not inherit
        # from w:sz. So a run with no w:szCs is sized by Word's default rather
        # than by the document's.
        for run in persian_runs(document(docx)):
            text = "".join(item.text or "" for item in run.iter(f"{W}t"))
            size = run.find(f"{W}rPr/{W}szCs")
            assert size is not None, f"{text!r} has no w:szCs"
            assert size.get(f"{W}val"), text

    def test_the_complex_script_size_matches_the_ascii_size(self, docx):
        # Diverging sizes are how a line of Persian ends up a size larger than
        # the English around it.
        for run in persian_runs(document(docx)):
            ascii_size = run.find(f"{W}rPr/{W}sz")
            cs_size = run.find(f"{W}rPr/{W}szCs")
            if ascii_size is not None:
                assert ascii_size.get(f"{W}val") == cs_size.get(f"{W}val")

    def test_the_script_is_marked_farsi(self, docx):
        for run in persian_runs(document(docx)):
            language = run.find(f"{W}rPr/{W}lang")
            assert language is not None
            assert language.get(f"{W}bidi") == "fa-IR", language.attrib


class TestMixedContent:
    """A run of Latin inside Persian, which the splitter produces.

    The title has to be Persian here: the writer takes the document's direction
    from the whole of its own text, title included, so an English title makes an
    otherwise Persian book left-to-right. The first version of these tests used
    the Persian title `"کتاب"` for the English case and reported a Persian title
    correctly marked RTL as a defect.
    """

    def test_the_latin_fragment_is_not_marked_rtl(self, tmp_path):
        target = build(tmp_path / "m.docx", titles=["این کتاب Chapter One است"])
        for run in document(target).iter(f"{W}r"):
            text = "".join(item.text or "" for item in run.iter(f"{W}t"))
            if not text.strip():
                continue
            if "Chapter" in text:
                # Marked RTL, Latin text reverses into gibberish -- the other
                # half of the same problem.
                assert not is_rtl(run), text
            if "این کتاب" in text:
                assert is_rtl(run), text

    def test_no_text_is_lost_by_the_split(self, tmp_path):
        target = build(tmp_path / "m.docx", titles=["این کتاب Chapter One است"])
        text = " ".join(item.text or "" for item in document(target).iter(f"{W}t"))
        text = re.sub(r"\s+", " ", text)
        for fragment in ("این کتاب", "Chapter One", "است"):
            assert fragment in text, fragment

    def test_an_english_document_does_not_get_rtl_runs(self, tmp_path):
        target = build(
            tmp_path / "e.docx", titles=["Plain English text"],
            to_lang="EN", title="Book",
        )
        markup = raw(target)
        # A document with no Arabic in it must not claim to be Arabic. The title
        # is English for the same reason: `fix_docx_typography` reads the whole
        # document's text, so a Persian title would make this book RTL and the
        # assertion would be measuring the title rather than the runs.
        assert not re.search(r"<w:rtl\s*/>", markup), (
            "an English document marked a run right-to-left"
        )
