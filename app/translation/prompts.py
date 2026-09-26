# ============================================================
# app/translation/prompts.py
# ============================================================

AUTHOR_VOICE_MARKER = "[AUTHOR_VOICE_PRESERVATION]"

AUTHOR_VOICE_GUIDANCE = f"""
{AUTHOR_VOICE_MARKER}
Preserve the author's voice, not only the literal meaning:
- Retain sentence rhythm, pacing, register, and stylistic density.
- Preserve the narrative point of view and the narrator's distance.
- Keep each character's dialogue distinct and consistent.
- Recreate humor, irony, ambiguity, subtext, and emotional intensity naturally.
- Do not flatten unusual but intentional stylistic choices into generic prose.
""".strip()


def with_author_voice(prompt: str) -> str:
    """Append concrete author-voice guidance once."""
    prompt = str(prompt or "").strip()
    if AUTHOR_VOICE_MARKER in prompt:
        return prompt
    return f"{prompt}\n\n{AUTHOR_VOICE_GUIDANCE}".strip()


def get_translation_prompt(
    from_lang,
    to_lang,
    filetype,
):
    """
    دریافت Prompt ترجمه از کاربر.

    کاربر می‌تواند هر Prompt دلخواهی برای ترجمه وارد کند.

    ورودی چندخطی است و با یک خط خالی پایان پیدا می‌کند.

    Args:
        from_lang (str):
            زبان مبدا.

        to_lang (str):
            زبان مقصد.

        filetype (str):
            نوع فایل، مانند epub یا pdf.

    Returns:
        str:
            Prompt نهایی ترجمه.
    """

    print()
    print("=" * 60)
    print("TRANSLATION PROMPT")
    print("=" * 60)

    print()
    print(f"Translation: {from_lang} -> {to_lang}")
    print(f"File type  : {filetype}")
    print()

    print("Enter your translation prompt.")
    print("You can paste a multi-line prompt.")
    print("Press ENTER on an empty line when finished.")
    print()

    prompt_lines = []

    while True:

        try:
            line = input()

        except EOFError:
            break

        # خط خالی = پایان Prompt
        if line == "":
            break

        prompt_lines.append(line)

    prompt = "\n".join(prompt_lines).strip()

    # ========================================================
    # اگر کاربر Prompt وارد نکرد
    # ========================================================

    if not prompt:

        print()
        print("No custom prompt entered.")
        print("Using default translation prompt.")
        print()

        return get_default_prompt(
            from_lang,
            to_lang,
            filetype,
        )

    # ========================================================
    # Prompt کاربر
    # ========================================================

    print()
    print("Custom translation prompt accepted.")
    print()

    return prompt


# ============================================================
# ============================================================
# ENGINE RULES
# ============================================================

ENGINE_RULES = """
Translation engine rules:

- [FORMAT: {FORMAT}] Input is a {FORMAT} document. Translate only
  its human-readable text and preserve every structural marker
  exactly (HTML/XML tags, attributes and hierarchy; Markdown
  syntax; timecodes).
- Do not translate attribute values, code blocks or script/style
  content.
- Apply the glossary strictly when one is provided.
- Never add, remove or summarize content; translate what is there.
- If a passage is ambiguous, keep the closest faithful meaning and
  append {{NOTE: short explanation}} after your translation of that
  passage.
- If the text appears cut off at the start or end of the chunk, do
  not guess the missing words; append {{BOUNDARY_WARNING}} instead.
- Keep proper nouns, brand names and technical terms unless the
  glossary overrides them.
- Return ONLY the translated content without explanations or code
  fences.
""".strip()


def _with_engine_rules(prompt, filetype):
    """
    Append the translation engine rules to any prompt.
    """

    prompt = str(prompt or "").strip()

    format_tag = str(filetype).upper().lstrip(".")

    return (
        f"{prompt}\n\n"
        f"{ENGINE_RULES.format(FORMAT=format_tag)}"
    ).strip()


def get_engine_prompt(
    from_lang,
    to_lang,
    filetype,
):
    """
    Build the standalone professional translation-engine prompt.
    """

    filetype = str(
        filetype
    ).lower().lstrip(".")

    format_tag = filetype.upper()

    if filetype == "srt":

        behavior = """
SRT (subtitle) behavior:

- Each chunk is one subtitle text.
- Translate ONLY the text lines.
- Never alter the index or the timecodes.
- Keep line breaks where the original has them.
- Maximum translated line length: 42 characters per line.
- If a translated line exceeds this, break it naturally at a
  phrase boundary.
""".strip()

    elif filetype == "pdf":

        behavior = """
PDF behavior:

- Preserve paragraph structure as much as possible.
- Greek and Latin quotations do not need to be translated.
- Preserve them as they appear in the source.
""".strip()

    else:

        behavior = """
HTML/XML behavior (EPUB):

- Preserve all HTML/XML tags, tag names, attributes, attribute
  values, tag hierarchy, element order, IDs and classes.
- Do not modify the document structure.
- Translate only human-readable text.
""".strip()

    return (
        f"""
You are a professional translation engine. Translate the content
from {from_lang} to {to_lang} faithfully while preserving all
formatting markers.

[FORMAT: {format_tag}]

{behavior}

{ENGINE_RULES.format(FORMAT=format_tag)}
""".strip()
    )


# DEFAULT PROMPT
# ============================================================

def get_default_prompt(
    from_lang,
    to_lang,
    filetype,
):
    """
    Prompt پیش‌فرض در صورتی که کاربر Prompt وارد نکند.
    """

    filetype = str(
        filetype
    ).lower().lstrip(".")

    # ========================================================
    # EPUB
    # ========================================================

    if filetype == "epub":

        return _with_engine_rules(f"""
You are an expert literary and academic translator.

Translate the provided content from {from_lang} to {to_lang}.

Translation requirements:

1. Preserve the exact meaning of the original text.
2. Produce natural, fluent and readable Persian.
3. Do not translate word-by-word when doing so creates unnatural Persian.
4. Preserve the author's tone and writing style.
5. Keep terminology consistent throughout the entire book.
6. Do not summarize the text.
7. Do not add information that does not exist in the source.
8. Do not remove information from the source.
9. Translate only the human-readable content.

HTML/XML requirements:

- Preserve all HTML/XML tags.
- Preserve tag names.
- Preserve attributes.
- Preserve attribute values.
- Preserve tag hierarchy.
- Preserve element order.
- Preserve IDs.
- Preserve classes.
- Preserve links and references.
- Do not modify the document structure.

Translate only human-readable text.

Greek and Latin quotations do not need to be translated.
Preserve them as they appear in the source.

Return ONLY the translated content.
Do not add explanations.
Do not add comments.
Do not use Markdown code fences.
""".strip(), filetype)

    # ========================================================
    # PDF
    # ========================================================

    if filetype == "pdf":

        return _with_engine_rules(f"""
You are an expert literary and academic translator.

Translate the provided content from {from_lang} to {to_lang}.

Translation requirements:

1. Preserve the exact meaning of the original text.
2. Produce natural, fluent and readable Persian.
3. Preserve the author's tone and writing style.
4. Keep terminology consistent throughout the book.
5. Do not translate word-by-word when doing so creates unnatural Persian.
6. Do not summarize.
7. Do not add information.
8. Do not remove information.
9. Preserve paragraph structure as much as possible.

Greek and Latin quotations do not need to be translated.
Preserve them as they appear in the source.

Return ONLY the translated content.
Do not add explanations.
Do not add comments.
Do not use Markdown code fences.
""".strip(), filetype)

    # ========================================================
    # GENERIC
    # ========================================================

    return _with_engine_rules(f"""
You are an expert translator.

Translate the provided content from {from_lang} to {to_lang}.

Preserve:

- Meaning
- Tone
- Style
- Terminology
- Paragraph structure
- Formatting
- References

Translate naturally and accurately.

Do not summarize.
Do not add information.
Do not remove information.
Do not explain your translation.

Return ONLY the translated content.

Do not use Markdown code fences.
""".strip(), filetype)
