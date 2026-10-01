import re
import uuid
import zipfile
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from fontTools.ttLib import TTFont

from app.output.typography import has_rtl, text_direction


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("w", W)
ET.register_namespace("r", REL)
LATIN_PARTS = re.compile(r"(https?://[^\s<>]+|[A-Za-z0-9]+(?:[ .:/@_+#=\-]+[A-Za-z0-9]+)*)")
PROPERTY_ORDER = {
    "pPr": "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange",
    "rPr": "rStyle rFonts b bCs i iCs caps smallCaps strike dStrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath rPrChange",
    "tblPr": "tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription tblPrChange",
}


def tag(name):
    return f"{{{W}}}{name}"


def child(parent, name, first=False):
    element = parent.find(tag(name))
    if element is None:
        element = ET.Element(tag(name))
        if first:
            parent.insert(0, element)
        else:
            parent.append(element)
    return element


#: The properties whose ``w:val`` is a flag rather than a number, a name or an
#: identifier. Everything else in this file must have its value written through
#: verbatim: collapsing ``abstractNumId="992"`` to ``"0"`` makes every list point
#: at a numbering definition that does not exist, and Word drops the numbering.
BOOLEAN_PROPERTIES = frozenset({
    "bidi", "rtl", "bCs", "iCs", "bidiVisual", "embedTrueTypeFonts",
    "noProof", "rtlGutter", "mirrorIndents",
})


def value(parent, name, setting):
    """Set a property's value, writing a boolean the way Word writes one.

    A WordprocessingML boolean may carry ``w:val`` with ``1``/``0`` -- ECMA-376
    allows it -- but Word itself writes the bare element, and for ``w:rtl``
    specifically it treats the explicit form as off. That is not cosmetic:
    ``w:rtl`` is what tells Word a run is right-to-left text, and without it the
    complex-script font and size are not selected and the Arabic shaping engine
    does not run. The letters come out in isolated forms -- shaped, but not
    readable.

    Measured on the reported titles: with ``w:val="1"`` the document carried 5
    explicit ones and no bare ones, and Word laid every one of them out
    left-to-right.

    The flag handling is confined to :data:`BOOLEAN_PROPERTIES`. An earlier
    version treated every value as a flag, and turned ``abstractNumId="992"``
    into ``"0"`` -- so every list pointed at a numbering definition that did not
    exist. The test that would have caught it asserted a boolean in a document
    that had no boolean left to assert on.
    """
    element = child(parent, name)
    if name not in BOOLEAN_PROPERTIES:
        element.set(tag("val"), str(setting))
        return
    if setting in (1, "1", True):
        # Bare: the value is implied, which is how Word writes it and the only
        # form it honours for `rtl`.
        element.attrib.pop(tag("val"), None)
    else:
        element.set(tag("val"), "0")


def xml_bytes(root):
    for name, order in PROPERTY_ORDER.items():
        ranks = {tag(value): index for index, value in enumerate(order.split())}
        for element in root.iter(tag(name)):
            element[:] = sorted(element, key=lambda item: ranks.get(item.tag, len(ranks)))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def font_properties(properties, bidi_language: str = "fa-IR"):
    """Set the font on a run or paragraph, and its complex-script language.

    ``bidi_language`` follows the document rather than being hardcoded.

    It was `fa-IR` always, and this function is called on every ``<w:rPr>`` in
    ``word/styles.xml`` as well as in the document. So an English or Persian-free
    book came out declaring its complex script Persian throughout its style
    table -- which is how a document about Latin text ends up with Persian
    hyphenation, Persian line breaking, and a proofing language the reader never
    asked for.
    """
    fonts = child(properties, "rFonts", first=True)
    fonts.attrib.clear()
    for name in ("ascii", "hAnsi", "cs", "eastAsia"):
        fonts.set(tag(name), "Vazirmatn")
    child(properties, "lang").set(tag("bidi"), bidi_language)
    for normal, complex_script in (("b", "bCs"), ("i", "iCs"), ("sz", "szCs")):
        existing = properties.find(tag(normal))
        if existing is not None:
            child(properties, complex_script).attrib.update(existing.attrib)

    # `w:szCs` is the size Word uses for complex script, and for a run marked RTL
    # it is the *only* size it uses. It used to be created solely as a copy of
    # `w:sz`, so a run that declared no size at all -- which is every run this
    # function touches, since the size lives in the style -- got no `w:szCs`
    # either, and the Persian text fell back to Word's own default rather than
    # the document's 12pt.
    if properties.find(tag("szCs")) is None:
        size = properties.find(tag("sz"))
        if size is not None:
            child(properties, "szCs").set(tag("val"), size.get(tag("val"), "24"))


@lru_cache(maxsize=8)
def font_bytes(weight):
    path = Path(__file__).parents[1] / "library" / f"Vazirmatn-{weight}.woff2"
    with TTFont(path) as font:
        if font["OS/2"].fsType & 2:
            raise ValueError("Font does not permit embedding")
        font.flavor = None
        output = BytesIO()
        font.save(output)
        return output.getvalue()


#: The faces embedded: the weight, the schema slot it is filed under, and the
#: family name it is filed as.
#:
#: ECMA-376 §17.8.1 gives ``CT_Font`` exactly four embedded-font children --
#: ``embedRegular``, ``embedBold``, ``embedItalic``, ``embedBoldItalic``, in that
#: order -- and no others. The five-weight table this replaces used
#: ``embedMedium``, ``embedSemiBold`` and ``embedBlack``, none of which are in the
#: schema, so Word rejected the entire package: "The file appears to be
#: corrupted." Isolated by substitution -- the writer's own output, the style
#: pass, the settings change and the zip rewrite were each confirmed good, and
#: ``embed_fonts`` alone was enough to make Word refuse the file.
#:
#: A weight the schema has no slot for becomes its own family, which is how Word
#: stores several weights of one typeface. Nothing names those families yet, so
#: they are carried but not yet selected; the two slots the schema does have
#: carry the two faces the styles actually ask for.
EMBEDDED_FACES = (
    ("Regular", "embedRegular", "Vazirmatn"),
    ("Bold", "embedBold", "Vazirmatn"),
    ("Medium", "embedRegular", "Vazirmatn Medium"),
    ("SemiBold", "embedRegular", "Vazirmatn SemiBold"),
    ("Black", "embedRegular", "Vazirmatn Black"),
)

#: The order ``CT_Font`` requires its children in. A face's slot has to be written
#: at the right index or the part is invalid, and an invalid ``fontTable.xml``
#: makes Word reject the whole document.
FONT_CHILD_ORDER = ("altName", "panose1", "charset", "family", "notTrueType",
                    "pitch", "sig", "embedRegular", "embedBold", "embedItalic",
                    "embedBoldItalic")

#: What Word writes for a sans-serif family of this kind, and what it expects to
#: find. All optional in the schema; included because a bare ``w:font`` carrying
#: nothing but an embed slot is not a shape Word produces.
FONT_DESCRIPTORS = (
    ("panose1", {"val": "020B0604020202020204"}),
    ("charset", {"val": "00"}),
    ("family", {"val": "swiss"}),
    ("pitch", {"val": "variable"}),
)


def _font_entry(fonts, name):
    """The ``w:font`` for a family, created with Word's usual descriptors."""
    entry = next((item for item in fonts if item.get(tag("name")) == name), None)
    if entry is None:
        entry = ET.SubElement(fonts, tag("font"), {tag("name"): name})
        for child_name, attributes in FONT_DESCRIPTORS:
            ET.SubElement(entry, tag(child_name), {tag(k): v for k, v in attributes.items()})
    return entry


def _sort_font_children(entry):
    """Put a ``w:font``'s children in the order ``CT_Font`` declares.

    The schema is a sequence, so ``embedBold`` after ``embedRegular`` is fine but
    an embed slot ahead of ``panose1`` is not, and an invalid ``fontTable.xml``
    makes Word reject the whole document rather than just the font.
    """
    ranks = {tag(name): index for index, name in enumerate(FONT_CHILD_ORDER)}
    entry[:] = sorted(entry, key=lambda item: ranks.get(item.tag, len(ranks)))


def embed_fonts(parts):
    fonts = ET.fromstring(parts.get("word/fontTable.xml", f'<w:fonts xmlns:w="{W}"/>'.encode()))
    relationships = ET.fromstring(parts.get("word/_rels/fontTable.xml.rels", f'<Relationships xmlns="{PACKAGE_REL}"/>'.encode()))
    used_ids = {item.get("Id") for item in relationships}
    for weight, embed, family in EMBEDDED_FACES:
        identifier = uuid.uuid4()
        data = bytearray(font_bytes(weight))
        # ECMA-376 §17.8.1: XOR the first 32 bytes with the fontKey's 16 bytes,
        # reversed, applied twice.
        key = identifier.bytes[::-1]
        for index in range(32):
            data[index] ^= key[index % 16]
        name = f"Vazirmatn-{weight}.odttf"
        parts[f"word/fonts/{name}"] = bytes(data)
        relation_id = f"kalima{weight}"
        while relation_id in used_ids:
            relation_id += "Font"
        used_ids.add(relation_id)
        ET.SubElement(relationships, f"{{{PACKAGE_REL}}}Relationship", {
            "Id": relation_id, "Type": f"{REL}/font", "Target": f"fonts/{name}",
        })
        entry = _font_entry(fonts, family)
        embedded = child(entry, embed)
        embedded.set(f"{{{REL}}}id", relation_id)
        # `w:fontKey` is of type `ST_Guid`, whose pattern is the canonical GUID
        # form -- braces *and* dashes: \{8-4-4-4-12\}. An earlier change stripped
        # the dashes on the reasoning that 32 bare hex digits were expected; that
        # is not the type, and Word validates the pattern and refuses to open the
        # document when it does not match -- "The file appears to be corrupted",
        # with no hint that the font table is at fault. The obfuscation key is
        # derived from the same value, so the dashes are removed only here, for
        # the XOR.
        embedded.set(
            tag("fontKey"),
            "{" + str(identifier).upper() + "}",
        )
    for entry in fonts:
        _sort_font_children(entry)
    parts["word/fontTable.xml"] = xml_bytes(fonts)
    parts["word/_rels/fontTable.xml.rels"] = xml_bytes(relationships)
    content_types = ET.fromstring(parts["[Content_Types].xml"])
    if not any(item.get("Extension") == "odttf" for item in content_types):
        ET.SubElement(content_types, f"{{{CONTENT_TYPES}}}Default", {
            "Extension": "odttf", "ContentType": "application/vnd.openxmlformats-officedocument.obfuscatedFont",
        })
    if not any(item.get("PartName") == "/word/fontTable.xml" for item in content_types):
        ET.SubElement(content_types, f"{{{CONTENT_TYPES}}}Override", {
            "PartName": "/word/fontTable.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml",
        })
    parts["[Content_Types].xml"] = xml_bytes(content_types)
    document_rels = ET.fromstring(parts["word/_rels/document.xml.rels"])
    if not any(item.get("Type") == f"{REL}/fontTable" for item in document_rels):
        ET.SubElement(document_rels, f"{{{PACKAGE_REL}}}Relationship", {
            "Id": "kalimaFontTable", "Type": f"{REL}/fontTable", "Target": "fontTable.xml",
        })
    parts["word/_rels/document.xml.rels"] = xml_bytes(document_rels)
    settings = ET.fromstring(parts["word/settings.xml"])
    value(settings, "embedTrueTypeFonts", 1)
    embedded = settings.find(tag("embedTrueTypeFonts"))
    settings.remove(embedded)
    before = {"embedSystemFonts", "saveSubsetFonts", "saveFormsData", "mirrorMargins", "defaultTabStop", "compat", "rsids", "themeFontLang", "clrSchemeMapping", "decimalSymbol", "listSeparator"}
    position = next((index for index, item in enumerate(settings) if item.tag in {tag(name) for name in before}), len(settings))
    settings.insert(position, embedded)
    parts["word/settings.xml"] = xml_bytes(settings)


def fix_run(run, bidi_language="fa-IR", size_half_points=None):
    """Normalise one run: font, complex-script size, direction.

    ``size_half_points`` is the document's own size, carried in because the run
    usually has none -- it lives in the style, not on the run -- and a run marked
    RTL is sized from ``w:szCs`` alone. Without it, Persian text is sized by
    whatever Word's own default is rather than by the 12pt the document declares.
    """
    properties = child(run, "rPr", first=True)
    if size_half_points and properties.find(tag("sz")) is None:
        child(properties, "sz").set(tag("val"), str(size_half_points))
    font_properties(properties, bidi_language)
    text_elements = run.findall(tag("t"))
    if len(text_elements) != 1 or any(item.tag not in {tag("rPr"), tag("t")} for item in run):
        value(properties, "rtl", int(has_rtl("".join(element.text or "" for element in text_elements))))
        return [run]
    text = text_elements[0].text or ""
    result = []
    for fragment in filter(None, LATIN_PARTS.split(text)):
        replacement = deepcopy(run)
        replacement.find(tag("t")).text = fragment
        replacement.find(tag("t")).set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        value(replacement.find(tag("rPr")), "rtl", int(has_rtl(fragment)))
        child(replacement.find(tag("rPr")), "lang").set(tag("val"), "fa-IR" if has_rtl(fragment) else "en-US")
        result.append(replacement)
    return result or [run]


def rtl_numbering(numbering, num_id, mapping):
    if num_id in mapping:
        return mapping[num_id]
    original = next((item for item in numbering.findall(tag("num")) if item.get(tag("numId")) == num_id), None)
    if original is None:
        return num_id
    abstract_id = original.find(tag("abstractNumId")).get(tag("val"))
    abstract = next((item for item in numbering.findall(tag("abstractNum")) if item.get(tag("abstractNumId")) == abstract_id), None)
    if abstract is None:
        return num_id
    new_abstract = deepcopy(abstract)
    new_abstract_id = str(max(int(item.get(tag("abstractNumId"))) for item in numbering.findall(tag("abstractNum"))) + 1)
    new_abstract.set(tag("abstractNumId"), new_abstract_id)
    for level in new_abstract.findall(tag("lvl")):
        value(level, "lvlJc", "right")
        properties = child(level, "pPr")
        value(properties, "bidi", 1)
        indent = child(properties, "ind")
        indent.set(tag("right"), indent.attrib.pop(tag("left"), "720"))
        indent.set(tag("left"), "0")
    numbering.insert(len(numbering.findall(tag("abstractNum"))), new_abstract)
    new_num = deepcopy(original)
    new_num_id = str(max(int(item.get(tag("numId"))) for item in numbering.findall(tag("num"))) + 1)
    new_num.set(tag("numId"), new_num_id)
    value(new_num, "abstractNumId", new_abstract_id)
    numbering.append(new_num)
    mapping[num_id] = new_num_id
    return new_num_id


def _declared_size(parts) -> int | None:
    """The document's own font size, in half-points, or None if it declares none.

    Read from ``docDefaults`` first and then ``Normal``, which is where a Word
    document puts it. A run inherits neither on its own: ``w:szCs`` is what a
    right-to-left run is sized by, and it is not inherited from ``w:sz``.
    """
    try:
        styles = ET.fromstring(parts["word/styles.xml"])
    except (KeyError, ET.ParseError):
        return None
    for path in (f"{tag('rPrDefault')}/{tag('rPr')}/{tag('sz')}", f"{tag('style')}/{tag('rPr')}/{tag('sz')}"):
        found = styles.find(path)
        if found is not None and found.get(tag("val")):
            try:
                return int(found.get(tag("val")))
            except ValueError:
                continue
    return None


def fix_docx_typography(path):
    with zipfile.ZipFile(path) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    document = ET.fromstring(parts["word/document.xml"])
    text = " ".join(item.text or "" for item in document.iter(tag("t")))
    rtl_document = has_rtl(text)
    # The complex-script language for every run and style in the document. Taken
    # from the document's own text, because it is used on the style table too --
    # and a style declaring Persian for an English book is how Latin text ends up
    # with Persian hyphenation.
    bidi_language = "fa-IR" if rtl_document else "en-US"
    # The document's declared size, so a run can be given the same one for its
    # complex script. Read from the style table rather than hardcoded, because
    # that is where the size actually is.
    document_size = _declared_size(parts)
    if not rtl_document:
        # No direction to fix -- but the font still has to be embedded.

        # This returned early, unconditionally, and the early return skipped
        # `embed_fonts` as well. So an English or Persian-free book came out
        # declaring a font it did not carry, which is the same complaint from a
        # reader who cannot read the characters: "the output has no good font".
        # The direction work is still skipped, because there is none to do; the
        # font work is not, because it is not about direction.
        styles_ltr = ET.fromstring(parts["word/styles.xml"])
        for properties in styles_ltr.iter(tag("rPr")):
            font_properties(properties, bidi_language)
        parts["word/styles.xml"] = xml_bytes(styles_ltr)
        embed_fonts(parts)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in parts.items():
                archive.writestr(name, data)
        return path
    default_direction = text_direction(text)
    numbering = ET.fromstring(parts["word/numbering.xml"]) if "word/numbering.xml" in parts else None
    number_mapping = {}
    for paragraph in document.iter(tag("p")):
        content = " ".join(item.text or "" for item in paragraph.iter(tag("t")))
        rtl = text_direction(content, default_direction) == "rtl"
        properties = child(paragraph, "pPr", first=True)
        value(properties, "bidi", int(rtl))
        alignment = child(properties, "jc")
        if alignment.get(tag("val")) not in {"center", "both", "distribute"}:
            alignment.set(tag("val"), "right" if rtl else "left")
        spacing = child(properties, "spacing")
        spacing.set(tag("line"), "360")
        spacing.set(tag("lineRule"), "auto")
        num = properties.find(f'{tag("numPr")}/{tag("numId")}')
        if rtl and num is not None and numbering is not None:
            num.set(tag("val"), rtl_numbering(numbering, num.get(tag("val")), number_mapping))
        for parent in list(paragraph.iter()):
            for run in list(parent):
                if run.tag == tag("r"):
                    position = list(parent).index(run)
                    parent.remove(run)
                    for offset, replacement in enumerate(
                        fix_run(run, bidi_language, document_size)
                    ):
                        parent.insert(position + offset, replacement)
    for table in document.iter(tag("tbl")):
        content = " ".join(item.text or "" for item in table.iter(tag("t")))
        properties = child(table, "tblPr", first=True)
        value(properties, "bidiVisual", int(text_direction(content, default_direction) == "rtl"))
    styles = ET.fromstring(parts["word/styles.xml"])
    defaults = child(styles, "docDefaults", first=True)
    paragraph_defaults = child(child(defaults, "pPrDefault"), "pPr")
    value(paragraph_defaults, "bidi", int(default_direction == "rtl"))
    value(paragraph_defaults, "jc", "right" if default_direction == "rtl" else "left")
    for properties in styles.iter(tag("rPr")):
        font_properties(properties, bidi_language)
    parts["word/document.xml"] = xml_bytes(document)
    parts["word/styles.xml"] = xml_bytes(styles)
    if numbering is not None:
        parts["word/numbering.xml"] = xml_bytes(numbering)
    embed_fonts(parts)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return path
