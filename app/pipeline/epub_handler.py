import zipfile
from io import BytesIO

from app.pipeline.html_processor import split_html_by_paragraph


def _chunk_settings():
    """The chunking settings, read once per call so tests can change them."""
    from app.core.config import get_chunking_config
    return get_chunking_config()


def _split_for_build(html, max_chunk_size):
    """Split a document the way this run will split it again on save.

    Returns ``(pieces, contexts)``. ``contexts`` maps a piece's index to the plain
    text of the pieces before it, and is empty unless semantic chunking is on.

    The one rule that matters here: the split used to build the job and the split
    used to save it must be identical, because saving works by re-splitting the
    original file and overwriting the pieces by position. The old code did not
    guarantee that -- ``build_chunks`` took a ``max_chunk_size`` argument, but
    ``save_translated_epub`` re-split with the module default, so any caller that
    passed a different size silently lost every translation past the first
    mismatch. Both sides now go through this one function.
    """
    settings = _chunk_settings()

    if not settings["semantic_chunking"]:
        pieces = split_html_by_paragraph(html, max_chunk_size)
        return pieces, {}

    from app.pipeline.semantic_chunker import SemanticChunker

    chunker = SemanticChunker(
        max_tokens=settings["chunk_max_tokens"],
        context_window=settings["chunk_context_window"],
    )
    chunks = chunker.chunk(html)
    return [c.html for c in chunks], {
        index: c.context_before for index, c in enumerate(chunks) if c.context_before
    }


class EPUBHandler:

    @staticmethod
    def extract_content(epub_path):

        content_files = []

        with zipfile.ZipFile(epub_path, 'r') as zip_ref:

            html_files = [
                f for f in zip_ref.namelist()
                if f.endswith(('.html', '.xhtml'))
            ]

            for html_file in html_files:

                try:

                    with zip_ref.open(html_file) as file:

                        content = file.read().decode('utf-8')

                        content_files.append(
                            (html_file, content)
                        )

                except Exception as e:

                    print(
                        f"Warning: Could not process "
                        f"{html_file}: {e}"
                    )

                    continue

        return content_files


    @staticmethod
    def build_chunks(
        input_epub_path,
        max_chunk_size=10000
    ):

        content_files = EPUBHandler.extract_content(
            input_epub_path
        )

        all_chunks = []

        chapter_map = {}

        # chunk_id -> the plain text of the preceding chunks, for the model to
        # read but never to translate. Empty unless semantic chunking is on.
        contexts = {}

        chunk_counter = 0

        for html_file, content in content_files:

            print(
                f"Processing {html_file} [build_chunks]"
            )

            chunks, file_contexts = _split_for_build(
                content,
                max_chunk_size
            )

            print(
                f"Split into {len(chunks)} chunks "
                f"[build_chunks]"
            )

            for pos, chunk in enumerate(chunks):

                chunk_id = f'chunk-{chunk_counter}'

                chunk_id = str(chunk_id)

                all_chunks.append(
                    (chunk_id, chunk)
                )

                chapter_map[chunk_id] = (
                    html_file,
                    pos
                )

                context = file_contexts.get(pos)
                if context:
                    contexts[chunk_id] = context

                chunk_counter += 1

        print(
            f"Total chunks created: "
            f"{len(all_chunks)} [build_chunks]"
        )

        if contexts:
            print(
                f"{len(contexts)} chunk(s) carry preceding "
                f"context for the model [build_chunks]"
            )

        return all_chunks, chapter_map, contexts


    @staticmethod
    def save_translated_epub(
        input_epub_path,
        output_epub_path,
        translations,
        chapter_map,
        max_chunk_size=10000
    ):

        file_chunks = {}

        for chunk_id, (filename, pos) in chapter_map.items():

            if filename not in file_chunks:
                file_chunks[filename] = {}

            if chunk_id in translations:

                file_chunks[filename][pos] = (
                    translations[chunk_id]
                )

        with zipfile.ZipFile(
            input_epub_path,
            'r'
        ) as zip_in:

            with zipfile.ZipFile(
                output_epub_path,
                'w'
            ) as zip_out:

                for item in zip_in.infolist():

                    if item.filename in file_chunks:

                        content = zip_in.read(
                            item.filename
                        ).decode('utf-8')

                        # The same splitter the build used, with the same size.
                        #
                        # This used to call split_html_by_paragraph(content) with
                        # the module default, ignoring the size the job was built
                        # with. A caller that passed anything but 10000 therefore
                        # re-split into a different number of pieces, and every
                        # translation past the first divergence was written to the
                        # wrong paragraph or dropped -- silently, because the
                        # positions were in range.
                        chunks, _ = _split_for_build(
                            content,
                            max_chunk_size
                        )

                        for pos, chunk in file_chunks[
                            item.filename
                        ].items():

                            if pos < len(chunks):

                                chunks[pos] = chunk

                        translated_content = ''.join(
                            chunks
                        )

                        new_info = zipfile.ZipInfo(
                            filename=item.filename,
                            date_time=item.date_time
                        )

                        new_info.compress_type = (
                            item.compress_type
                        )

                        zip_out.writestr(
                            new_info,
                            translated_content.encode('utf-8')
                        )

                    else:

                        buffer = BytesIO(
                            zip_in.read(item.filename)
                        )

                        new_info = zipfile.ZipInfo(
                            filename=item.filename,
                            date_time=item.date_time
                        )

                        new_info.compress_type = (
                            item.compress_type
                        )

                        zip_out.writestr(
                            new_info,
                            buffer.getvalue()
                        )
