# ============================================================
# app/pipeline/pdf_fixer.py
# ============================================================

import json
import re
import subprocess
from pathlib import Path

import fitz  # PyMuPDF


# ============================================================
# 1. خواندن لیست صفحات مشکل‌دار
# ============================================================

def read_fix_pages(fix_pages_path):
    """
    لیست شماره صفحات نیازمند اصلاح را از فایل fixpdfpages.txt می‌خواند.

    فرمت فایل:
        1,5,8,12

    خروجی:
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
# 2. جمع‌آوری HTML صفحات موردنظر
# ============================================================

def collect_input_pages(fixjobpath, pages_to_fix):
    """
    فایل HTML مربوط به صفحات موردنظر را از پوشه Job جمع‌آوری می‌کند.

    مثال:
        page_0001.html
        page_0005.html
        page_0010.html

    خروجی:
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
# 3. ذخیره صفحات ورودی
# ============================================================

def save_input_pages(fixjobpath, input_pages):
    """
    صفحات جمع‌آوری‌شده را در فایل input_pages.json ذخیره می‌کند.

    هدف:
        داشتن Snapshot از صفحات ورودی قبل از ترجمه.
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
# 4. حذف Markdown Code Fence از خروجی مدل
# ============================================================

def clean_translated_html(translated_html):
    """
    Markdown Code Fence را از خروجی مدل حذف می‌کند.

    مثال:

        ```html
        <p>Hello</p>
        ```

    تبدیل می‌شود به:

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
# 5. ترجمه صفحات با OpenAI
# ============================================================

def translate_pages(
    client,
    input_pages,
    system_message,
    fixjobpath,
    model
):
    """
    صفحات HTML را یکی‌یکی از طریق OpenAI ترجمه می‌کند.

    Parameters
    ----------
    client:
        OpenAI-compatible client

    input_pages:
        لیست صفحات HTML

    system_message:
        Prompt سیستم مربوط به اصلاح PDF

    fixjobpath:
        مسیر Job

    model:
        مدل مورد استفاده

    Returns
    -------
    dict
        دیکشنری صفحات اصلاح‌شده
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
        # ارسال صفحه به مدل
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
        # دریافت خروجی مدل
        # ----------------------------------------------------

        translated_html = (
            response
            .choices[0]
            .message
            .content
        )

        # ----------------------------------------------------
        # پاک کردن Markdown Code Fence
        # ----------------------------------------------------

        translated_html = clean_translated_html(
            translated_html
        )

        # ----------------------------------------------------
        # ذخیره نتیجه
        # ----------------------------------------------------

        fixed_pages[page_num] = translated_html

        # ----------------------------------------------------
        # ذخیره مداوم Progress
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
# 6. بارگذاری ترجمه‌های قبلی
# ============================================================

def load_fixed_pages(fixed_pages_path):
    """
    ترجمه‌های قبلی ذخیره‌شده در fixed_pages.json را می‌خواند.

    اگر فایل وجود نداشته باشد:
        None

    در غیر این صورت:
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
# 7. جایگزینی صفحات اصلاح‌شده در PDF
# ============================================================

def replace_pdf_pages(
    input_pdf_path,
    fixed_pages,
    output_pdf_path
):
    """
    صفحات اصلاح‌شده را در PDF اصلی جایگزین می‌کند.

    فرآیند:

        PDF اصلی
            ↓
        حذف صفحه مشکل‌دار
            ↓
        ایجاد صفحه جدید
            ↓
        قرار دادن HTML ترجمه‌شده
            ↓
        ذخیره PDF جدید
    """

    # --------------------------------------------------------
    # باز کردن PDF
    # --------------------------------------------------------

    doc = fitz.open(
        input_pdf_path
    )

    # --------------------------------------------------------
    # ابعاد صفحه
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
    # مرتب‌سازی صفحات
    # --------------------------------------------------------
    #
    # این بخش مهم است.
    #
    # اگر صفحات را از بزرگ به کوچک پردازش کنیم،
    # حذف صفحات باعث نمی‌شود index صفحات بعدی جابه‌جا شود.
    #
    # مثال:
    #
    # pages = 2, 5, 8
    #
    # ابتدا 8
    # سپس 5
    # سپس 2
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
        # بررسی معتبر بودن شماره صفحه
        # ----------------------------------------------------

        if page_index < 0 or page_index >= len(doc):

            print(
                f"Warning: Invalid PDF page index "
                f"{page_index}. Skipping."
            )

            continue

        # ----------------------------------------------------
        # حذف صفحه اصلی
        # ----------------------------------------------------

        doc.delete_page(
            page_index
        )

        # ----------------------------------------------------
        # ایجاد صفحه جدید در همان موقعیت
        # ----------------------------------------------------

        page = doc.new_page(
            pno=page_index,
            width=page_width,
            height=page_height
        )

        # ----------------------------------------------------
        # قرار دادن HTML
        # ----------------------------------------------------

        try:
            page.insert_htmlbox(
                fitz.Rect(margin, margin, page_width - margin, page_height - margin),
                translated_html,
            )
        except RuntimeError as exc:
            if "destination" not in str(exc).lower() and "target_id" not in str(exc).lower():
                raise
            safe_html = re.sub(r'</?a\b[^>]*>', '', translated_html, flags=re.IGNORECASE)
            page.insert_htmlbox(
                fitz.Rect(margin, margin, page_width - margin, page_height - margin),
                safe_html,
            )

    # --------------------------------------------------------
    # ذخیره PDF اصلاح‌شده
    # --------------------------------------------------------

    doc.save(
        output_pdf_path
    )

    doc.close()

    print(
        f"Fixed PDF saved to {output_pdf_path}"
    )


# ============================================================
# 8. فشرده‌سازی PDF
# ============================================================

def compress_pdf(
    input_pdf_path,
    output_pdf_path
):
    """
    PDF اصلاح‌شده را با Ghostscript فشرده می‌کند.

    هدف:
        کاهش حجم PDF خروجی.
    """

    try:

        subprocess.run(
            [
                'gs',

                # نوع خروجی
                '-sDEVICE=pdfwrite',

                # نسخه سازگاری PDF
                '-dCompatibilityLevel=1.4',

                # تنظیم کیفیت/حجم
                '-dPDFSETTINGS=/screen',

                # Subset فونت‌ها
                '-dSubsetFonts=true',

                # Embed کردن فونت‌ها
                '-dEmbedAllFonts=true',

                # فشرده‌سازی فونت‌ها
                '-dCompressFonts=true',

                # جلوگیری از توقف
                '-dNOPAUSE',

                # حذف خروجی‌های غیرضروری
                '-dQUIET',

                # اجرای Batch
                '-dBATCH',

                # فایل خروجی
                f'-sOutputFile={output_pdf_path}',

                # فایل ورودی
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
# 9. اجرای کامل فرآیند Fix PDF
# ============================================================

def fix_pdf(
    client,
    fixjobpath,
    fixinput,
    model,
    system_message
):
    """
    فرآیند کامل اصلاح صفحات PDF را اجرا می‌کند.

    ترتیب:

        fixpdfpages.txt
                ↓
        پیدا کردن صفحات
                ↓
        خواندن HTML
                ↓
        ترجمه / اصلاح
                ↓
        ذخیره fixed_pages.json
                ↓
        جایگزینی صفحات PDF
                ↓
        فشرده‌سازی PDF

    Parameters
    ----------
    client:
        OpenAI-compatible client

    fixjobpath:
        مسیر Job

    fixinput:
        مسیر PDF ورودی

    model:
        مدل ترجمه

    system_message:
        Prompt مربوط به اصلاح PDF

    Returns
    -------
    tuple[Path, Path]
        مسیر PDF اصلاح‌شده و PDF فشرده‌شده
    """

    # --------------------------------------------------------
    # تبدیل مسیرها به Path
    # --------------------------------------------------------

    fixjobpath = Path(
        fixjobpath
    )

    fixinput = Path(
        fixinput
    )

    # --------------------------------------------------------
    # فایل‌های موردنیاز
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
    # بررسی Job
    # --------------------------------------------------------

    if not fixjobpath.exists():

        raise FileNotFoundError(
            f"Fix job directory not found: "
            f"{fixjobpath}"
        )

    # --------------------------------------------------------
    # بررسی PDF
    # --------------------------------------------------------

    if not fixinput.exists():

        raise FileNotFoundError(
            f"Input PDF not found: "
            f"{fixinput}"
        )

    # --------------------------------------------------------
    # بررسی Prompt
    # --------------------------------------------------------

    if not system_message:

        raise ValueError(
            "PDF fix system prompt is empty."
        )

    # --------------------------------------------------------
    # بررسی ترجمه‌های قبلی
    # --------------------------------------------------------

    fixed_pages = load_fixed_pages(
        fixed_pages_path
    )

    # ========================================================
    # اگر ترجمه قبلی وجود نداشته باشد
    # ========================================================

    if fixed_pages is None:

        # ----------------------------------------------------
        # بررسی fixpdfpages.txt
        # ----------------------------------------------------

        if not fix_pages_path.exists():

            raise FileNotFoundError(
                f"fixpdfpages.txt not found in "
                f"{fixjobpath}"
            )

        # ----------------------------------------------------
        # خواندن صفحات مشکل‌دار
        # ----------------------------------------------------

        pages_to_fix = read_fix_pages(
            fix_pages_path
        )

        print(
            f"Pages selected for fixing: "
            f"{pages_to_fix}"
        )

        # ----------------------------------------------------
        # جمع‌آوری HTML صفحات
        # ----------------------------------------------------

        input_pages = collect_input_pages(
            fixjobpath,
            pages_to_fix
        )

        # ----------------------------------------------------
        # بررسی اینکه صفحه‌ای پیدا شده یا نه
        # ----------------------------------------------------

        if not input_pages:

            raise ValueError(
                "No input HTML pages were found "
                "for PDF fixing."
            )

        # ----------------------------------------------------
        # ذخیره Snapshot
        # ----------------------------------------------------

        save_input_pages(
            fixjobpath,
            input_pages
        )

        # ----------------------------------------------------
        # ترجمه صفحات
        # ----------------------------------------------------

        fixed_pages = translate_pages(
            client=client,
            input_pages=input_pages,
            system_message=system_message,
            fixjobpath=fixjobpath,
            model=model
        )

    # ========================================================
    # بررسی نتیجه ترجمه
    # ========================================================

    if not fixed_pages:

        raise ValueError(
            "No fixed pages available."
        )

    # --------------------------------------------------------
    # مسیر PDF اصلاح‌شده
    # --------------------------------------------------------

    output_pdf_path = fixinput.with_name(
        f"{fixinput.stem}_fixed.pdf"
    )

    # --------------------------------------------------------
    # جایگزینی صفحات
    # --------------------------------------------------------

    replace_pdf_pages(
        input_pdf_path=fixinput,
        fixed_pages=fixed_pages,
        output_pdf_path=output_pdf_path
    )

    # --------------------------------------------------------
    # مسیر PDF فشرده‌شده
    # --------------------------------------------------------

    compressed_pdf_path = fixinput.with_name(
        f"{fixinput.stem}_fixed_compressed.pdf"
    )

    # --------------------------------------------------------
    # فشرده‌سازی
    # --------------------------------------------------------

    compress_pdf(
        input_pdf_path=output_pdf_path,
        output_pdf_path=compressed_pdf_path
    )

    # --------------------------------------------------------
    # نتیجه نهایی
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
