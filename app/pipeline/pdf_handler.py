import base64
from pathlib import Path
import fitz  # PyMuPDF
from openai import OpenAI
import re
import subprocess
from datetime import datetime

class PDFHandler:
    """Handler for PDF file processing"""

    @staticmethod
    def generate_page_images(pdf_path, output_dir, max_height=2000, dpi=150):
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        with fitz.open(pdf_path) as pdf:
            page_count = len(pdf)
            for page_num in range(page_count):
                page = pdf.load_page(page_num)
                
                # Calculate the scaling factor for the desired DPI
                scale = dpi / 72  # Default DPI in PyMuPDF is 72
                
                # Generate the pixmap with the scaling factor
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                
                # Resize image if height exceeds max_height
                if pix.height > max_height:
                    scale = max_height / pix.height
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                
                image_path = output_dir / f"page_{page_num:04d}.png"
                pix.save(image_path)
                #print(f"Saved image: {image_path}")

        print(f"{page_count} pages saved as images in {output_dir.name}")

    @staticmethod
    def encode_image(image_path):
        """Encode image to base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    @staticmethod
    def remove_line_height_styles(html_content):
        """Remove all line-height styles from the HTML content"""
        return re.sub(r'line-height:\s*\d+(\.\d+)?;', '', html_content)

    @staticmethod
    def sanitize_html_output(html_content):
        """Sanitize the HTML output by removing markdown code block markers and line-height styles"""
        lines = html_content.split('\n')
        if lines[0].strip() == "```html":
            lines = lines[1:]
        if lines[-1].strip() == "```":
            lines = lines[:-1]
        sanitized_content = '\n'.join(lines)
        return PDFHandler.remove_line_height_styles(sanitized_content)

    @staticmethod
    def compress_pdf(input_pdf_path, output_pdf_path):
        """Compress PDF using Ghostscript with font consolidation"""
        try:
            subprocess.run([
                'gs',
                '-sDEVICE=pdfwrite',
                '-dCompatibilityLevel=1.4',
                '-dPDFSETTINGS=/screen',
                '-dSubsetFonts=true',
                '-dEmbedAllFonts=true',
                '-dCompressFonts=true',
                '-dNOPAUSE',
                '-dQUIET',
                '-dBATCH',
                f'-sOutputFile={output_pdf_path}',
                input_pdf_path
            ], check=True)
            print(f"Compressed PDF saved to {output_pdf_path.name}")
        except subprocess.CalledProcessError as e:
            print(f"Error compressing PDF: {e}")

    @staticmethod
    def save_translated_pdf(translations, output_pdf_path):
        """Write a new PDF document from HTML pages"""
        output_pdf_path = Path(output_pdf_path)  # Ensure it's a Path object
        temp_pdf_path = output_pdf_path.with_suffix('.temp.pdf')  # Temporary file for uncompressed PDF
        output_pdf_path.parent.mkdir(exist_ok=True)
        doc = fitz.open()
        page_width = 6.5 * 72  # inches to points
        page_height = 9.5 * 72
        margin = 0.5 * 72

        for chunk_id in sorted(translations.keys(), key=lambda x: int(x.split('-')[1])):
            html_content = translations[chunk_id]
            page = doc.new_page(width=page_width, height=page_height)
            # Insert HTML content into the page with a bounding box
            page.insert_htmlbox(fitz.Rect(margin, margin, page_width - margin, page_height - margin), html_content)
        
        # Save the uncompressed PDF to a temporary file
        doc.save(temp_pdf_path)
        print(f"Uncompressed PDF saved to {temp_pdf_path.name}")

        # Compress the PDF using Ghostscript
        PDFHandler.compress_pdf(temp_pdf_path, output_pdf_path)

    @staticmethod
    def save_bilingual_pdf(original_pdf_path, translations, output_pdf_path):
        """Write a new PDF document alternating between original and translated pages."""
        output_pdf_path = Path(output_pdf_path)  # Ensure it's a Path object
        temp_pdf_path = output_pdf_path.with_suffix('.temp.pdf')  # Temporary file for uncompressed PDF
        original_pdf_path = Path(original_pdf_path)
        output_pdf_path.parent.mkdir(exist_ok=True)
        doc = fitz.open()
        page_width = 6.5 * 72  # inches to points
        page_height = 9.5 * 72
        margin = 0.5 * 72

        # Open the original PDF
        original_doc = fitz.open(original_pdf_path)

        for page_num in range(len(original_doc)):
            # Add original page
            original_page = original_doc.load_page(page_num)
            doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)

            # Add translated page
            chunk_id = f'chunk-{page_num}'
            if chunk_id in translations:
                html_content = translations[chunk_id]
                page = doc.new_page(width=page_width, height=page_height)
                # Insert HTML content into the page with a bounding box
                page.insert_htmlbox(fitz.Rect(margin, margin, page_width - margin, page_height - margin), html_content)

        # Save the uncompressed PDF to a temporary file
        doc.save(temp_pdf_path)
        print(f"Uncompressed PDF saved to {temp_pdf_path.name}")

        # Compress the PDF using Ghostscript
        PDFHandler.compress_pdf(temp_pdf_path, output_pdf_path)

    @staticmethod
    def transcribe_pdf(client, input_pdf_path, paths, dpi=150, batch=False):
        input_pdf_path = Path(input_pdf_path)
        if not input_pdf_path.exists():
            print(f"Error: Input file not found: {input_pdf_path}")
            return

        # Create output directory
        output_dir = paths['job_dir']
        #output_dir.mkdir(exist_ok=True)

        # Clear temporary image dir
        for png_file in output_dir.glob("*.png"):
            png_file.unlink()

        # Generate images of PDF pages
        PDFHandler.generate_page_images(input_pdf_path, output_dir, dpi=dpi)

        all_chunks = []
        chapter_map = {}

        custompdfprompt = None
        custom_pdfprompt_path = Path("./custompdfprompt.txt")
        if custom_pdfprompt_path.exists():
            print(f"Using custompdfprompt.txt [transcribe_pdf]")
            with open(custom_pdfprompt_path, 'r', encoding='utf-8') as f:
                custompdfprompt = f.read()

        # if batch:
        #     # Create batch input file
        #     temp_dir = Path('./temp')
        #     temp_dir.mkdir(exist_ok=True)
        #     timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        #     batch_file_path = temp_dir / f"batch_input_{timestamp}.jsonl"
            
        #     with open(batch_file_path, "w", encoding="utf-8") as f:
        #         for page_num, image_path in enumerate(sorted(output_dir.glob("*.png"))):
        #             base64_image = PDFHandler.encode_image(image_path)
        #             request = {
        #                 "custom_id": f"chunk-{page_num}",
        #                 "method": "POST",
        #                 "url": "/v1/chat/completions",
        #                 "body": {
        #                     "model": "gpt-5.6-terra",
        #                     "messages": [
        #                         {
        #                             "role": "system",
        #                             "content": "The image is a scan of a page from a German scholarly book on Greek and Roman antiquity. Most of the text is in German, but there are also quotations in Greek and Latin. Your task is to understand the text, translate into ENGLISH while leaving any Greek and Latin quotations untranslated, and format the translated text as a HTML document as it would be in a scholarly translation. Accuracy is key. Pay special attention to FOOTNOTES, which are found at the bottom of the page in SMALLER font. Use 'font-family: serif' for the main text and 'font-family: Palatino' for Greek text. Do not use tables or line-height or any heading tags (e.g. <h1>). Return ONLY the HTML content, beginning with <!DOCTYPE html> and ending with </html>."
        #                         },
        #                         {
        #                             "role": "user",
        #                             "content": "Analyze the following image.",
        #                             "type": "image_url",
        #                             "image_url": {
        #                                 "url": f"data:image/png;base64,{base64_image}"
        #                             }
        #                         }
        #                     ]
        #                 }
        #             }
        #             f.write(json.dumps(request) + "\n")
            
        #     print(f"Batch input file created at {batch_file_path}")
        #     return batch_file_path

        # Process each image sequentially
        for page_num, image_path in enumerate(sorted(output_dir.glob("*.png"))):
            base64_image = PDFHandler.encode_image(image_path)
            #print(f"Transcribing {image_path}")

            print(f"Processing page {page_num + 1} of {len(list(output_dir.glob('*.png')))}")

            response = client.chat.completions.create(
                model="gpt-5.6-terra",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": custompdfprompt if custompdfprompt else "The image is a scan of a page from a German scholarly book on Greek and Roman antiquity. Most of the text is in German, but there are also quotations in Greek and Latin. Your task is to understand the text, translate into ENGLISH while leaving Greek and Latin quotations untranslated, and format the translated text as a HTML document as it would be in a scholarly translation. Accuracy is key. Pay special attention to FOOTNOTES, which are found at the bottom of the page in SMALLER font. If you encounter fragments of sentences, do not leave them out but do your best to translate them. Use 'font-family: serif' for the main text and 'font-family: Palatino' for Greek text. Do not use tables or line-height or any heading tags (e.g. <h1>). Return ONLY the HTML content, beginning with <!DOCTYPE html> and ending with </html>.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                            },
                        ],
                    }
                ],
            )

            html_content = response.choices[0].message.content
            sanitized_html_content = PDFHandler.sanitize_html_output(html_content)

            # Save HTML content to file
            html_file_path = output_dir / f"page_{page_num:04d}.html"
            with open(html_file_path, "w", encoding="utf-8") as html_file:
                html_file.write(sanitized_html_content)

            # Add to all_chunks and chapter_map
            chunk_id = f'chunk-{page_num}'
            all_chunks.append((chunk_id, sanitized_html_content))
            chapter_map[chunk_id] = {
                "item": f"page_{page_num}.html",
                "pos": 0
            }

        return all_chunks, chapter_map

if __name__ == "__main__":
    PDFHandler.main()

