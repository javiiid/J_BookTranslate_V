from app.pipeline.epub_handler import EPUBHandler


def reassemble_translation(
    input_epub_path,
    output_epub_path,
    chapter_map,
    translations
):
    """
    Reassemble translated chunks into a new EPUB.

    Parameters
    ----------
    input_epub_path : str or Path
        مسیر EPUB اصلی

    output_epub_path : str or Path
        مسیر EPUB خروجی

    chapter_map : dict
        نقشه محل قرارگیری Chunkها

    translations : dict
        ترجمه Chunkها
    """

    EPUBHandler.save_translated_epub(
        input_epub_path=input_epub_path,
        output_epub_path=output_epub_path,
        translations=translations,
        chapter_map=chapter_map
    )

    print(
        f"Processed translation output saved to "
        f"{output_epub_path} [reassemble_translation]"
    )
