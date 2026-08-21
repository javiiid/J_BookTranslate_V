import zipfile
from io import BytesIO

from app.pipeline.html_processor import split_html_by_paragraph


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

        chunk_counter = 0

        for html_file, content in content_files:

            print(
                f"Processing {html_file} [build_chunks]"
            )

            chunks = split_html_by_paragraph(
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

                chunk_counter += 1

        print(
            f"Total chunks created: "
            f"{len(all_chunks)} [build_chunks]"
        )

        return all_chunks, chapter_map


    @staticmethod
    def save_translated_epub(
        input_epub_path,
        output_epub_path,
        translations,
        chapter_map
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

                        chunks = split_html_by_paragraph(
                            content
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
