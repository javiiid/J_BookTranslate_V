# ============================================================
# app/translation/prompts.py
# ============================================================

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

        return f"""
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
""".strip()

    # ========================================================
    # PDF
    # ========================================================

    if filetype == "pdf":

        return f"""
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
""".strip()

    # ========================================================
    # GENERIC
    # ========================================================

    return f"""
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
""".strip()