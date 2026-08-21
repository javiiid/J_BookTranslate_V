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
        Ù…Ø³ÛŒØ± EPUB Ø§ØµÙ„ÛŒ

    output_epub_path : str or Path
        Ù…Ø³ÛŒØ± EPUB Ø®Ø±ÙˆØ¬ÛŒ

    chapter_map : dict
        Ù†Ù‚Ø´Ù‡ Ù…Ø­Ù„ Ù‚Ø±Ø§Ø±Ú¯ÛŒØ±ÛŒ ChunkÙ‡Ø§

    translations : dict
        ØªØ±Ø¬Ù…Ù‡ ChunkÙ‡Ø§
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
