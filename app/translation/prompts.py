from pathlib import Path

def system_prompt(from_lang, to_lang, filetype):
    custom_prompt_path = Path("./customprompt.txt")
    custom_epubprompt_path = Path("./customepubprompt.txt")
    custom_pdfprompt_path = Path("./custompdfprompt.txt")
    if (custom_prompt_path.exists()):
        print(f"Using customprompt.txt [system_prompt]")
        with open(custom_prompt_path, 'r', encoding='utf-8') as f:
            return f.read()

    if filetype == 'epub':
        if (custom_epubprompt_path.exists()):
            print(f"Using customepubprompt.txt [system_prompt]")
            with open(custom_epubprompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return f"""You are an academic translator, translating to {to_lang}.
CRITICAL: You must preserve ALL HTML/XML structure exactly as provided.
You don't need to translate quotations in Greek or Latin.
If you find numbers which look like footnote markers, and make them superscript.
"""
    elif filetype == 'pdf':
        if (custom_pdfprompt_path.exists()):
            print(f"Using custompdfprompt.txt [system_prompt]")
            with open(custom_pdfprompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return f"""You are an academic translator, translating to {to_lang}.
CRITICAL: You must preserve ALL HTML/XML structure exactly as provided.
You don't need to translate quotations in Greek or Latin.
"""

