# ============================================================
# app/pipeline/pdf_fixer.py
# ============================================================

import json
import re
import subprocess
from pathlib import Path

import fitz  # PyMuPDF


# ============================================================
# 1. Ø®ÙˆØ§Ù†Ø¯Ù† Ù„ÛŒØ³Øª ØµÙØ­Ø§Øª Ù…Ø´Ú©Ù„â€ŒØ¯Ø§Ø±
# ============================================================

def read_fix_pages(fix_pages_path):
    """
    Ù„ÛŒØ³Øª Ø´Ù…Ø§Ø±Ù‡ ØµÙØ­Ø§Øª Ù†ÛŒØ§Ø²Ù…Ù†Ø¯ Ø§ØµÙ„Ø§Ø­ Ø±Ø§ Ø§Ø² ÙØ§ÛŒÙ„ fixpdfpages.txt Ù…ÛŒâ€ŒØ®ÙˆØ§Ù†Ø¯.

    ÙØ±Ù…Øª ÙØ§ÛŒÙ„:
        1,5,8,12

    Ø®Ø±ÙˆØ¬ÛŒ:
        [1, 5, 8, 12]
    """

    with open(
        fix_pages_path,
        'r',
        encoding='utf-8'
    ) as file:

        pages = file.read().strip().split(',')

        return [
            int(page.strip())
            for page in pages
        ]


# ============================================================
# 2. Ø¬Ù…Ø¹â€ŒØ¢ÙˆØ±ÛŒ HTML ØµÙØ­Ø§Øª Ù…ÙˆØ±Ø¯Ù†Ø¸Ø±
# ============================================================

def collect_input_pages(fixjobpath, pages_to_fix):
    """
    ÙØ§ÛŒÙ„ HTML Ù…Ø±Ø¨ÙˆØ· Ø¨Ù‡ ØµÙØ­Ø§Øª Ù…ÙˆØ±Ø¯Ù†Ø¸Ø± Ø±Ø§ Ø§Ø² Ù¾ÙˆØ´Ù‡ Job Ø¬Ù…Ø¹â€ŒØ¢ÙˆØ±ÛŒ Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

    Ù…Ø«Ø§Ù„:
        page_0001.html
        page_0005.html
        page_0010.html

    Ø®Ø±ÙˆØ¬ÛŒ:
        [
            ('0001', '<html>...</html>'),
            ('0005', '<html>...</html>')
        ]
    """

    input_pages = []

    for page_num in pages_to_fix:

        page_file = (
            fixjobpath /
            f'page_{page_num:04d}.html'
        )

        if page_file.exists():

            with open(
                page_file,
                'r',
                encoding='utf-8'
            ) as file:

                html_content = file.read()

                input_pages.append(
                    (
                        f'{page_num:04d}',
                        html_content
                    )
                )

        else:

            print(
                f"Warning: Page file not found: {page_file}"
            )

    return input_pages


# ============================================================
# 3. Ø°Ø®ÛŒØ±Ù‡ ØµÙØ­Ø§Øª ÙˆØ±ÙˆØ¯ÛŒ
# ============================================================

def save_input_pages(fixjobpath, input_pages):
    """
    ØµÙØ­Ø§Øª Ø¬Ù…Ø¹â€ŒØ¢ÙˆØ±ÛŒâ€ŒØ´Ø¯Ù‡ Ø±Ø§ Ø¯Ø± ÙØ§ÛŒÙ„ input_pages.json Ø°Ø®ÛŒØ±Ù‡ Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

    Ù‡Ø¯Ù:
        Ø¯Ø§Ø´ØªÙ† Snapshot Ø§Ø² ØµÙØ­Ø§Øª ÙˆØ±ÙˆØ¯ÛŒ Ù‚Ø¨Ù„ Ø§Ø² ØªØ±Ø¬Ù…Ù‡.
    """

    input_pages_path = (
        fixjobpath /
        'input_pages.json'
    )

    with open(
        input_pages_path,
        'w',
        encoding='utf-8'
    ) as file:

        json.dump(
            input_pages,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"Saved input pages to {input_pages_path}"
    )


# ============================================================
# 4. Ø­Ø°Ù Markdown Code Fence Ø§Ø² Ø®Ø±ÙˆØ¬ÛŒ Ù…Ø¯Ù„
# ============================================================

def clean_translated_html(translated_html):
    """
    Markdown Code Fence Ø±Ø§ Ø§Ø² Ø®Ø±ÙˆØ¬ÛŒ Ù…Ø¯Ù„ Ø­Ø°Ù Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

    Ù…Ø«Ø§Ù„:

        ```html
        <p>Hello</p>
        ```

    ØªØ¨Ø¯ÛŒÙ„ Ù…ÛŒâ€ŒØ´ÙˆØ¯ Ø¨Ù‡:

        <p>Hello</p>
    """

    if not translated_html:
        return translated_html

    translated_html = re.sub(
        r'^```[a-zA-Z]*\s*\n',
        '',
        translated_html
    )

    translated_html = re.sub(
        r'\n```\s*$',
        '',
        translated_html
    )

    translated_html = re.sub(
        r'^```\s*$',
        '',
        translated_html
    )

    return translated_html.strip()


# ============================================================
# 5. ØªØ±Ø¬Ù…Ù‡ ØµÙØ­Ø§Øª Ø¨Ø§ OpenAI
# ============================================================

def translate_pages(
    client,
    input_pages,
    system_message,
    fixjobpath,
    model
):
    """
    ØµÙØ­Ø§Øª HTML Ø±Ø§ ÛŒÚ©ÛŒâ€ŒÛŒÚ©ÛŒ Ø§Ø² Ø·Ø±ÛŒÙ‚ OpenAI ØªØ±Ø¬Ù…Ù‡ Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

    Parameters
    ----------
    client:
        OpenAI-compatible client

    input_pages:
        Ù„ÛŒØ³Øª ØµÙØ­Ø§Øª HTML

    system_message:
        Prompt Ø³ÛŒØ³ØªÙ… Ù…Ø±Ø¨ÙˆØ· Ø¨Ù‡ Ø§ØµÙ„Ø§Ø­ PDF

    fixjobpath:
        Ù…Ø³ÛŒØ± Job

    model:
        Ù…Ø¯Ù„ Ù…ÙˆØ±Ø¯ Ø§Ø³ØªÙØ§Ø¯Ù‡

    Returns
    -------
    dict
        Ø¯ÛŒÚ©Ø´Ù†Ø±ÛŒ ØµÙØ­Ø§Øª Ø§ØµÙ„Ø§Ø­â€ŒØ´Ø¯Ù‡
    """

    fixed_pages = {}

    fixed_pages_path = (
        fixjobpath /
        'fixed_pages.json'
    )

    total_pages = len(input_pages)

    for index, (
        page_num,
        html_content
    ) in enumerate(input_pages):

        remaining_pages = (
            total_pages - index
        )

        print(
            f"Translating page {page_num} "
            f"({remaining_pages} pages remaining)"
        )

        # ----------------------------------------------------
        # Ø§Ø±Ø³Ø§Ù„ ØµÙØ­Ù‡ Ø¨Ù‡ Ù…Ø¯Ù„
        # ----------------------------------------------------

        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": html_content
                }
            ]
        )

        # ----------------------------------------------------
        # Ø¯Ø±ÛŒØ§ÙØª Ø®Ø±ÙˆØ¬ÛŒ Ù…Ø¯Ù„
        # ----------------------------------------------------

        translated_html = (
            response
            .choices[0]
            .message
            .content
        )

        # ----------------------------------------------------
        # Ù¾Ø§Ú© Ú©Ø±Ø¯Ù† Markdown Code Fence
        # ----------------------------------------------------

        translated_html = clean_translated_html(
            translated_html
        )

        # ----------------------------------------------------
        # Ø°Ø®ÛŒØ±Ù‡ Ù†ØªÛŒØ¬Ù‡
        # ----------------------------------------------------

        fixed_pages[page_num] = translated_html

        # ----------------------------------------------------
        # Ø°Ø®ÛŒØ±Ù‡ Ù…Ø¯Ø§ÙˆÙ… Progress
        # ----------------------------------------------------

        with open(
            fixed_pages_path,
            'w',
            encoding='utf-8'
        ) as file:

            json.dump(
                fixed_pages,
                file,
                indent=2,
                ensure_ascii=False
            )

        print(
            f"Saved fixed page {page_num} "
            f"to {fixed_pages_path}"
        )

    return fixed_pages


# ============================================================
# 6. Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ ØªØ±Ø¬Ù…Ù‡â€ŒÙ‡Ø§ÛŒ Ù‚Ø¨Ù„ÛŒ
# ============================================================

def load_fixed_pages(fixed_pages_path):
    """
    ØªØ±Ø¬Ù…Ù‡â€ŒÙ‡Ø§ÛŒ Ù‚Ø¨Ù„ÛŒ Ø°Ø®ÛŒØ±Ù‡â€ŒØ´Ø¯Ù‡ Ø¯Ø± fixed_pages.json Ø±Ø§ Ù…ÛŒâ€ŒØ®ÙˆØ§Ù†Ø¯.

    Ø§Ú¯Ø± ÙØ§ÛŒÙ„ ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø´ØªÙ‡ Ø¨Ø§Ø´Ø¯:
        None

    Ø¯Ø± ØºÛŒØ± Ø§ÛŒÙ† ØµÙˆØ±Øª:
        dict
    """

    if not fixed_pages_path.exists():
        return None

    print(
        f"Using existing fixed pages "
        f"from {fixed_pages_path}"
    )

    with open(
        fixed_pages_path,
        'r',
        encoding='utf-8'
    ) as file:

        return json.load(file)


# ============================================================
# 7. Ø¬Ø§ÛŒÚ¯Ø²ÛŒÙ†ÛŒ ØµÙØ­Ø§Øª Ø§ØµÙ„Ø§Ø­â€ŒØ´Ø¯Ù‡ Ø¯Ø± PDF
# ============================================================

def replace_pdf_pages(
    input_pdf_path,
    fixed_pages,
    output_pdf_path
):
    """
    ØµÙØ­Ø§Øª Ø§ØµÙ„Ø§Ø­â€ŒØ´Ø¯Ù‡ Ø±Ø§ Ø¯Ø± PDF Ø§ØµÙ„ÛŒ Ø¬Ø§ÛŒÚ¯Ø²ÛŒÙ† Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

    ÙØ±Ø¢ÛŒÙ†Ø¯:

        PDF Ø§ØµÙ„ÛŒ
            â†“
        Ø­Ø°Ù ØµÙØ­Ù‡ Ù…Ø´Ú©Ù„â€ŒØ¯Ø§Ø±
            â†“
        Ø§ÛŒØ¬Ø§Ø¯ ØµÙØ­Ù‡ Ø¬Ø¯ÛŒØ¯
            â†“
        Ù‚Ø±Ø§Ø± Ø¯Ø§Ø¯Ù† HTML ØªØ±Ø¬Ù…Ù‡â€ŒØ´Ø¯Ù‡
            â†“
        Ø°Ø®ÛŒØ±Ù‡ PDF Ø¬Ø¯ÛŒØ¯
    """

    # --------------------------------------------------------
    # Ø¨Ø§Ø² Ú©Ø±Ø¯Ù† PDF
    # --------------------------------------------------------

    doc = fitz.open(
        input_pdf_path
    )

    # --------------------------------------------------------
    # Ø§Ø¨Ø¹Ø§Ø¯ ØµÙØ­Ù‡
    # --------------------------------------------------------

    page_width = (
        6.5 * 72
    )

    page_height = (
        9.5 * 72
    )

    margin = (
        0.5 * 72
    )

    # --------------------------------------------------------
    # Ù…Ø±ØªØ¨â€ŒØ³Ø§Ø²ÛŒ ØµÙØ­Ø§Øª
    # --------------------------------------------------------
    #
    # Ø§ÛŒÙ† Ø¨Ø®Ø´ Ù…Ù‡Ù… Ø§Ø³Øª.
    #
    # Ø§Ú¯Ø± ØµÙØ­Ø§Øª Ø±Ø§ Ø§Ø² Ø¨Ø²Ø±Ú¯ Ø¨Ù‡ Ú©ÙˆÚ†Ú© Ù¾Ø±Ø¯Ø§Ø²Ø´ Ú©Ù†ÛŒÙ…ØŒ
    # Ø­Ø°Ù ØµÙØ­Ø§Øª Ø¨Ø§Ø¹Ø« Ù†Ù…ÛŒâ€ŒØ´ÙˆØ¯ index ØµÙØ­Ø§Øª Ø¨Ø¹Ø¯ÛŒ Ø¬Ø§Ø¨Ù‡â€ŒØ¬Ø§ Ø´ÙˆØ¯.
    #
    # Ù…Ø«Ø§Ù„:
    #
    # pages = 2, 5, 8
    #
    # Ø§Ø¨ØªØ¯Ø§ 8
    # Ø³Ù¾Ø³ 5
    # Ø³Ù¾Ø³ 2
    #
    # --------------------------------------------------------

    sorted_pages = sorted(
        fixed_pages.items(),
        key=lambda item: int(item[0]),
        reverse=True
    )

    for page_num, translated_html in sorted_pages:

        page_index = int(
            page_num
        )

        # ----------------------------------------------------
        # Ø¨Ø±Ø±Ø³ÛŒ Ù…Ø¹ØªØ¨Ø± Ø¨ÙˆØ¯Ù† Ø´Ù…Ø§Ø±Ù‡ ØµÙØ­Ù‡
        # ----------------------------------------------------

        if page_index < 0 or page_index >= len(doc):

            print(
                f"Warning: Invalid PDF page index "
                f"{page_index}. Skipping."
            )

            continue

        # ----------------------------------------------------
        # Ø­Ø°Ù ØµÙØ­Ù‡ Ø§ØµÙ„ÛŒ
        # ----------------------------------------------------

        doc.delete_page(
            page_index
        )

        # ----------------------------------------------------
        # Ø§ÛŒØ¬Ø§Ø¯ ØµÙØ­Ù‡ Ø¬Ø¯ÛŒØ¯ Ø¯Ø± Ù‡Ù…Ø§Ù† Ù…ÙˆÙ‚Ø¹ÛŒØª
        # ----------------------------------------------------

        page = doc.new_page(
            pno=page_index,
            width=page_width,
            height=page_height
        )

        # ----------------------------------------------------
        # Ù‚Ø±Ø§Ø± Ø¯Ø§Ø¯Ù† HTML
        # ----------------------------------------------------

        page.insert_htmlbox(
            fitz.Rect(
                margin,
                margin,
                page_width - margin,
                page_height - margin
            ),
            translated_html
        )

    # --------------------------------------------------------
    # Ø°Ø®ÛŒØ±Ù‡ PDF Ø§ØµÙ„Ø§Ø­â€ŒØ´Ø¯Ù‡
    # --------------------------------------------------------

    doc.save(
        output_pdf_path
    )

    doc.close()

    print(
        f"Fixed PDF saved to {output_pdf_path}"
    )


# ============================================================
# 8. ÙØ´Ø±Ø¯Ù‡â€ŒØ³Ø§Ø²ÛŒ PDF
# ============================================================

def compress_pdf(
    input_pdf_path,
    output_pdf_path
):
    """
    PDF Ø§ØµÙ„Ø§Ø­â€ŒØ´Ø¯Ù‡ Ø±Ø§ Ø¨Ø§ Ghostscript ÙØ´Ø±Ø¯Ù‡ Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

    Ù‡Ø¯Ù:
        Ú©Ø§Ù‡Ø´ Ø­Ø¬Ù… PDF Ø®Ø±ÙˆØ¬ÛŒ.
    """

    try:

        subprocess.run(
            [
                'gs',

                # Ù†ÙˆØ¹ Ø®Ø±ÙˆØ¬ÛŒ
                '-sDEVICE=pdfwrite',

                # Ù†Ø³Ø®Ù‡ Ø³Ø§Ø²Ú¯Ø§Ø±ÛŒ PDF
                '-dCompatibilityLevel=1.4',

                # ØªÙ†Ø¸ÛŒÙ… Ú©ÛŒÙÛŒØª/Ø­Ø¬Ù…
                '-dPDFSETTINGS=/screen',

                # Subset ÙÙˆÙ†Øªâ€ŒÙ‡Ø§
                '-dSubsetFonts=true',

                # Embed Ú©Ø±Ø¯Ù† ÙÙˆÙ†Øªâ€ŒÙ‡Ø§
                '-dEmbedAllFonts=true',

                # ÙØ´Ø±Ø¯Ù‡â€ŒØ³Ø§Ø²ÛŒ ÙÙˆÙ†Øªâ€ŒÙ‡Ø§
                '-dCompressFonts=true',

                # Ø¬Ù„ÙˆÚ¯ÛŒØ±ÛŒ Ø§Ø² ØªÙˆÙ‚Ù
                '-dNOPAUSE',

                # Ø­Ø°Ù Ø®Ø±ÙˆØ¬ÛŒâ€ŒÙ‡Ø§ÛŒ ØºÛŒØ±Ø¶Ø±ÙˆØ±ÛŒ
                '-dQUIET',

                # Ø§Ø¬Ø±Ø§ÛŒ Batch
                '-dBATCH',

                # ÙØ§ÛŒÙ„ Ø®Ø±ÙˆØ¬ÛŒ
                f'-sOutputFile={output_pdf_path}',

                # ÙØ§ÛŒÙ„ ÙˆØ±ÙˆØ¯ÛŒ
                str(input_pdf_path)
            ],
            check=True
        )

        print(
            f"Compressed PDF saved to "
            f"{output_pdf_path}"
        )

    except subprocess.CalledProcessError as e:

        print(
            f"Error compressing PDF: {e}"
        )

        raise


# ============================================================
# 9. Ø§Ø¬Ø±Ø§ÛŒ Ú©Ø§Ù…Ù„ ÙØ±Ø¢ÛŒÙ†Ø¯ Fix PDF
# ============================================================

def fix_pdf(
    client,
    fixjobpath,
    fixinput,
    model,
    system_message
):
    """
    ÙØ±Ø¢ÛŒÙ†Ø¯ Ú©Ø§Ù…Ù„ Ø§ØµÙ„Ø§Ø­ ØµÙØ­Ø§Øª PDF Ø±Ø§ Ø§Ø¬Ø±Ø§ Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

    ØªØ±ØªÛŒØ¨:

        fixpdfpages.txt
                â†“
        Ù¾ÛŒØ¯Ø§ Ú©Ø±Ø¯Ù† ØµÙØ­Ø§Øª
                â†“
        Ø®ÙˆØ§Ù†Ø¯Ù† HTML
                â†“
        ØªØ±Ø¬Ù…Ù‡ / Ø§ØµÙ„Ø§Ø­
                â†“
        Ø°Ø®ÛŒØ±Ù‡ fixed_pages.json
                â†“
        Ø¬Ø§ÛŒÚ¯Ø²ÛŒÙ†ÛŒ ØµÙØ­Ø§Øª PDF
                â†“
        ÙØ´Ø±Ø¯Ù‡â€ŒØ³Ø§Ø²ÛŒ PDF

    Parameters
    ----------
    client:
        OpenAI-compatible client

    fixjobpath:
        Ù…Ø³ÛŒØ± Job

    fixinput:
        Ù…Ø³ÛŒØ± PDF ÙˆØ±ÙˆØ¯ÛŒ

    model:
        Ù…Ø¯Ù„ ØªØ±Ø¬Ù…Ù‡

    system_message:
        Prompt Ù…Ø±Ø¨ÙˆØ· Ø¨Ù‡ Ø§ØµÙ„Ø§Ø­ PDF

    Returns
    -------
    tuple[Path, Path]
        Ù…Ø³ÛŒØ± PDF Ø§ØµÙ„Ø§Ø­â€ŒØ´Ø¯Ù‡ Ùˆ PDF ÙØ´Ø±Ø¯Ù‡â€ŒØ´Ø¯Ù‡
    """

    # --------------------------------------------------------
    # ØªØ¨Ø¯ÛŒÙ„ Ù…Ø³ÛŒØ±Ù‡Ø§ Ø¨Ù‡ Path
    # --------------------------------------------------------

    fixjobpath = Path(
        fixjobpath
    )

    fixinput = Path(
        fixinput
    )

    # --------------------------------------------------------
    # ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ù…ÙˆØ±Ø¯Ù†ÛŒØ§Ø²
    # --------------------------------------------------------

    fix_pages_path = (
        fixjobpath /
        'fixpdfpages.txt'
    )

    fixed_pages_path = (
        fixjobpath /
        'fixed_pages.json'
    )

    # --------------------------------------------------------
    # Ø¨Ø±Ø±Ø³ÛŒ Job
    # --------------------------------------------------------

    if not fixjobpath.exists():

        raise FileNotFoundError(
            f"Fix job directory not found: "
            f"{fixjobpath}"
        )

    # --------------------------------------------------------
    # Ø¨Ø±Ø±Ø³ÛŒ PDF
    # --------------------------------------------------------

    if not fixinput.exists():

        raise FileNotFoundError(
            f"Input PDF not found: "
            f"{fixinput}"
        )

    # --------------------------------------------------------
    # Ø¨Ø±Ø±Ø³ÛŒ Prompt
    # --------------------------------------------------------

    if not system_message:

        raise ValueError(
            "PDF fix system prompt is empty."
        )

    # --------------------------------------------------------
    # Ø¨Ø±Ø±Ø³ÛŒ ØªØ±Ø¬Ù…Ù‡â€ŒÙ‡Ø§ÛŒ Ù‚Ø¨Ù„ÛŒ
    # --------------------------------------------------------

    fixed_pages = load_fixed_pages(
        fixed_pages_path
    )

    # ========================================================
    # Ø§Ú¯Ø± ØªØ±Ø¬Ù…Ù‡ Ù‚Ø¨Ù„ÛŒ ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø´ØªÙ‡ Ø¨Ø§Ø´Ø¯
    # ========================================================

    if fixed_pages is None:

        # ----------------------------------------------------
        # Ø¨Ø±Ø±Ø³ÛŒ fixpdfpages.txt
        # ----------------------------------------------------

        if not fix_pages_path.exists():

            raise FileNotFoundError(
                f"fixpdfpages.txt not found in "
                f"{fixjobpath}"
            )

        # ----------------------------------------------------
        # Ø®ÙˆØ§Ù†Ø¯Ù† ØµÙØ­Ø§Øª Ù…Ø´Ú©Ù„â€ŒØ¯Ø§Ø±
        # ----------------------------------------------------

        pages_to_fix = read_fix_pages(
            fix_pages_path
        )

        print(
            f"Pages selected for fixing: "
            f"{pages_to_fix}"
        )

        # ----------------------------------------------------
        # Ø¬Ù…Ø¹â€ŒØ¢ÙˆØ±ÛŒ HTML ØµÙØ­Ø§Øª
        # ----------------------------------------------------

        input_pages = collect_input_pages(
            fixjobpath,
            pages_to_fix
        )

        # ----------------------------------------------------
        # Ø¨Ø±Ø±Ø³ÛŒ Ø§ÛŒÙ†Ú©Ù‡ ØµÙØ­Ù‡â€ŒØ§ÛŒ Ù¾ÛŒØ¯Ø§ Ø´Ø¯Ù‡ ÛŒØ§ Ù†Ù‡
        # ----------------------------------------------------

        if not input_pages:

            raise ValueError(
                "No input HTML pages were found "
                "for PDF fixing."
            )

        # ----------------------------------------------------
        # Ø°Ø®ÛŒØ±Ù‡ Snapshot
        # ----------------------------------------------------

        save_input_pages(
            fixjobpath,
            input_pages
        )

        # ----------------------------------------------------
        # ØªØ±Ø¬Ù…Ù‡ ØµÙØ­Ø§Øª
        # ----------------------------------------------------

        fixed_pages = translate_pages(
            client=client,
            input_pages=input_pages,
            system_message=system_message,
            fixjobpath=fixjobpath,
            model=model
        )

    # ========================================================
    # Ø¨Ø±Ø±Ø³ÛŒ Ù†ØªÛŒØ¬Ù‡ ØªØ±Ø¬Ù…Ù‡
    # ========================================================

    if not fixed_pages:

        raise ValueError(
            "No fixed pages available."
        )

    # --------------------------------------------------------
    # Ù…Ø³ÛŒØ± PDF Ø§ØµÙ„Ø§Ø­â€ŒØ´Ø¯Ù‡
    # --------------------------------------------------------

    output_pdf_path = fixinput.with_name(
        f"{fixinput.stem}_fixed.pdf"
    )

    # --------------------------------------------------------
    # Ø¬Ø§ÛŒÚ¯Ø²ÛŒÙ†ÛŒ ØµÙØ­Ø§Øª
    # --------------------------------------------------------

    replace_pdf_pages(
        input_pdf_path=fixinput,
        fixed_pages=fixed_pages,
        output_pdf_path=output_pdf_path
    )

    # --------------------------------------------------------
    # Ù…Ø³ÛŒØ± PDF ÙØ´Ø±Ø¯Ù‡â€ŒØ´Ø¯Ù‡
    # --------------------------------------------------------

    compressed_pdf_path = fixinput.with_name(
        f"{fixinput.stem}_fixed_compressed.pdf"
    )

    # --------------------------------------------------------
    # ÙØ´Ø±Ø¯Ù‡â€ŒØ³Ø§Ø²ÛŒ
    # --------------------------------------------------------

    compress_pdf(
        input_pdf_path=output_pdf_path,
        output_pdf_path=compressed_pdf_path
    )

    # --------------------------------------------------------
    # Ù†ØªÛŒØ¬Ù‡ Ù†Ù‡Ø§ÛŒÛŒ
    # --------------------------------------------------------

    print(
        "PDF fixing completed successfully."
    )

    print(
        f"Fixed PDF: {output_pdf_path}"
    )

    print(
        f"Compressed PDF: {compressed_pdf_path}"
    )

    return (
        output_pdf_path,
        compressed_pdf_path
    )
