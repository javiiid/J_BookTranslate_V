A modular Python application for translating EPUB and PDF books using OpenAI-compatible APIs.

The project is designed around a resumable translation pipeline, chunk-based processing, automatic progress saving, retry handling, batch translation support, and final document reconstruction.

---
---

# ⭐ Summary

J Book Translate is built around one core idea:

> **A long-running book translation should never lose completed work.**

Every translation chunk is processed independently, saved immediately, and can be resumed after an interruption or temporary API failure.

The current architecture provides a foundation for turning the project into a reliable, scalable book translation platform.
```

## ✨ Features

- 📚 EPUB translation
- 📄 PDF processing
- 🌍 Configurable source and target languages
- 🤖 Support for OpenAI-compatible APIs
- 🔌 Configurable AI models
- 🧩 Automatic document chunking
- 💾 Automatic progress persistence
- ▶️ Resume interrupted translations
- 🔄 Automatic API retry for temporary failures
- ⚡ Fast sequential translation mode
- 📦 Batch translation mode
- 🧪 Test translation mode
- 📝 Translation state stored locally
- 🗂️ Temporary job directories
- 🧹 Automatic cleanup after successful processing
- 🐛 Debug mode for preserving temporary files
- 📖 EPUB reconstruction after translation
- 📑 PDF translated/bilingual output
- ⌨️ Safe `Ctrl+C` interruption
- 🔐 API configuration separated from application logic

---

# 🏗️ Project Architecture

The project follows a modular architecture where each responsibility is separated into its own module.

```text
J_BookTranslate_V/
│
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── paths.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   │
│   ├── jobs/
│   │   ├── state.py
│   │   ├── manager.py
│   │   └── cleanup.py
│   │
│   ├── pipeline/
│   │   ├── pipeline.py
│   │   ├── epub_handler.py
│   │   ├── epub_pipeline.py
│   │   └── ...
│   │
│   └── translation/
│       ├── translator.py
│       ├── prompts.py
│       ├── batch.py
│       └── ...
│
├── temp/
│   └── ...
│
├── data/
│   └── ...
│
├── config.yaml
├── requirements.txt
├── README.md
└── .gitignore
```

---

# 🔄 Translation Pipeline

The general translation pipeline is:

```text
Input Book
    │
    ▼
File Type Detection
    │
    ├───────────────┐
    │               │
    ▼               ▼
   EPUB            PDF
    │               │
    ▼               ▼
Build Chunks    PDF Processing
    │               │
    ▼               ▼
Chapter / Page Mapping
    │
    ▼
Save Chunk State
    │
    ▼
Translation Engine
    │
    ├── Fast
    ├── Resume
    ├── Batch
    ├── Resume Batch
    └── Test
    │
    ▼
Save Translation
    │
    ▼
Reassemble Document
    │
    ▼
Output EPUB / PDF
    │
    ▼
Cleanup
```

---

# 📚 EPUB Processing

EPUB files are processed chapter by chapter.

Each XHTML/HTML document is extracted and divided into manageable chunks.

For example:

```text
OEBPS/ch01.xhtml
    └── chunk-0

OEBPS/ch01s01.xhtml
    ├── chunk-1
    ├── chunk-2
    ├── chunk-3
    ├── chunk-4
    ├── chunk-5
    └── chunk-6
```

The system maintains a `chapter_map` so that translated chunks can later be inserted into their original positions.

Example:

```python
chapter_map = {
    "chunk-0": ("OEBPS/ch01.xhtml", 0),
    "chunk-1": ("OEBPS/ch01s01.xhtml", 0),
    "chunk-2": ("OEBPS/ch01s01.xhtml", 1),
}
```

This allows the translated EPUB to preserve the original document structure.

---

# 🧩 Chunk-Based Translation

Instead of sending the entire book to the model at once, the book is divided into smaller chunks.

This provides several advantages:

- Lower memory usage
- Better API reliability
- Easier error recovery
- Lower risk of losing an entire translation
- Ability to resume from the last successful chunk
- Better progress visibility

Example:

```text
Total chunks: 48

chunk-0  ✅
chunk-1  ✅
chunk-2  ✅
chunk-3  ✅
chunk-4  ❌
...
```

Only unfinished chunks need to be translated again.

---

# 💾 Persistent Translation State

After every successful chunk, the translation state is saved.

Conceptually:

```text
chunk-0 → translated
chunk-1 → translated
chunk-2 → translated
```

is immediately written to disk.

This means that an unexpected shutdown, API failure, or manual interruption does not require the completed chunks to be translated again.

Typical job structure:

```text
temp/
└── book_FA_EN_gpt-4o_20260818_120000/
    │
    ├── chunks.json
    ├── translations.json
    ├── progress.log
    └── ...
```

---

# ▶️ Resume Translation

One of the main features of J Book Translate is resumable translation.

Suppose a book contains:

```text
48 chunks
```

and the application successfully translates:

```text
35 / 48
```

before being interrupted.

Running the application with:

```bash
--mode resume
```

will reuse the saved state.

The system checks which chunks already exist in `translations.json`.

For example:

```text
chunk-0  ✅
chunk-1  ✅
...
chunk-34 ✅
chunk-35 ❌
chunk-36 ❌
...
```

Only the missing chunks are translated.

---

# ⌨️ Safe Interruption

The application supports interruption using:

```text
Ctrl+C
```

When the translation is interrupted, the current progress is preserved.

Example:

```text
============================================================
TRANSLATION INTERRUPTED
Completed: 17/48
All completed translations have been saved.

Run again with:
--mode resume
to continue.
============================================================
```

This prevents unnecessary retranslation and API costs.

---

# 🔄 API Retry System

Temporary API failures are automatically retried.

The translator recognizes common temporary errors:

```text
429  Rate Limit
500  Internal Server Error
502  Bad Gateway
503  Service Unavailable
504  Gateway Timeout
```

The retry system uses exponential backoff.

Example:

```text
Attempt 1
   │
   └── 503
       │
       ▼
      wait 5s
       │
       ▼
Attempt 2
   │
   └── 503
       │
       ▼
      wait 10s
       │
       ▼
Attempt 3
```

This prevents the application from immediately sending repeated requests to an overloaded provider.

---

# 🧠 Model Configuration

The application accepts the model from the command line.

Example:

```bash
--model gpt-5.6-terra
```

The model is passed through the translation pipeline:

```text
main.py
   ↓
pipeline.py
   ↓
process_translations()
   ↓
translate_chunk()
   ↓
OpenAI-compatible API
```

The model is **not hardcoded inside the translation function**.

This allows different providers/models to be tested without changing the translation engine.

---

# 🔌 OpenAI-Compatible APIs

J Book Translate uses the OpenAI Python SDK.

Example client:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.gapgpt.app/v1",
    api_key="YOUR_API_KEY"
)
```

The application can therefore work with services exposing an OpenAI-compatible API.

---

# 🔐 API Key Security

Never hardcode API keys directly into source code.

Do NOT do this:

```python
client = OpenAI(
    base_url="https://api.example.com/v1",
    api_key="sk-xxxxxxxx"
)
```

Instead, store credentials in configuration or environment variables.

Example:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.example.com/v1
```

Then:

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)
```

### ⚠️ Important

API keys must never be committed to Git.

Add your configuration files to `.gitignore` when they contain secrets.

---

# 🌐 Language Configuration

The source and target languages can be specified from the command line.

Example:

```bash
--from-lang FA
--to-lang EN
```

Meaning:

```text
FA → Persian
EN → English
```

Another example:

```bash
--from-lang DE
--to-lang EN
```

The language settings are passed into the prompt system.

---

# 📝 Prompt System

Translation prompts are separated from the translation engine.

The prompt generator is located in:

```text
app/translation/prompts.py
```

The translator requests a system prompt using:

```python
system_message = system_prompt(
    from_lang,
    to_lang,
    filetype
)
```

This separation makes it possible to improve translation quality without modifying the API logic.

---

# ⚡ Translation Modes

J Book Translate supports several processing modes.

## Fast Mode

Fast mode translates chunks sequentially.

```bash
--mode fast
```

Typical flow:

```text
chunk-0
   ↓
save
   ↓
chunk-1
   ↓
save
   ↓
chunk-2
   ↓
save
```

Every successful chunk is saved immediately.

---

# ▶️ Resume Mode

Resume mode continues an existing translation.

```bash
--mode resume
```

Already translated chunks are skipped.

Example:

```text
Found 48 total chunks
Found 31 existing translations

Skipping already translated 31 chunks

Translating 17 chunks in 'resume' mode
```

---

# 📦 Batch Mode

Batch mode creates a batch request instead of processing each chunk synchronously.

```bash
--mode batch
```

This can be useful for large translation jobs.

The batch state is stored so that it can be checked later.

---

# 🔎 Batch Check

To check a previously created batch:

```bash
--mode batchcheck
```

The application retrieves the batch state and checks its status.

Possible statuses include:

```text
in_progress
completed
failed
```

If the batch is completed, its output is retrieved and merged with existing translations.

---

# ♻️ Resume Batch

If a batch translation is interrupted or partially completed:

```bash
--mode resumebatch
```

Only untranslated chunks are submitted again.

---

# 🧪 Test Mode

Test mode allows the translation pipeline to be tested without making API calls.

Expected file:

```text
<book-name>_translations.json
```

Example:

```text
leblanc-blonde-lady.epub
leblanc-blonde-lady_translations.json
```

This is useful for:

- Testing EPUB reconstruction
- Testing chapter mapping
- Testing translation state
- Testing the output pipeline
- Avoiding API costs during development

---

# 📄 PDF Support

The application also contains a PDF processing pipeline.

PDF processing can include:

```text
PDF
 ↓
Transcription / extraction
 ↓
HTML / chunks
 ↓
Translation pipeline
 ↓
Translated PDF
```

The PDF pipeline supports translated and bilingual output.

Example mode:

```bash
--mode pdfbilingual
```

---

# 📖 EPUB Reconstruction

After all chunks have been translated, the application reconstructs the original EPUB.

The process uses:

```python
reassemble_translation(
    input_path,
    output_path,
    chapter_map,
    translations
)
```

The original EPUB structure is preserved as much as possible while translated content is inserted into the appropriate locations.

---

# 🗂️ Job Management

Every translation creates a unique job ID.

Example:

```text
leblanc-blonde-lady_FA_EN_gpt-5.6-terra_20260818_120005
```

The ID contains:

```text
Input name
Source language
Target language
Model
Timestamp
```

This makes jobs easier to identify and resume.

---

# 🧹 Cleanup System

After successful processing, temporary files can be removed automatically.

The cleanup system handles:

- Temporary job directories
- Uploaded API files
- Batch output files
- Temporary processing files

In debug mode, temporary files are preserved.

---

# 🐛 Debug Mode

Debug mode is useful during development.

When enabled, temporary files are preserved.

This allows inspection of:

```text
chunks.json
translations.json
progress.log
batch state
```

without immediately deleting them.

---

# 📊 Progress Tracking

The application prints progress directly to the terminal.

Example:

```text
============================================================

Translating chunk 17/48
Chunk ID: chunk-16
Completed: 16/48

============================================================
```

After successful translation:

```text
Chunk chunk-16 translated successfully.
Saved progress: 17/48 chunks
```

This makes long-running translation jobs observable.

---

# 🚀 Installation

## 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd J_BookTranslate_V
```

---

## 2. Create a virtual environment

Windows:

```bash
python -m venv .venv
```

Activate:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then:

```powershell
.venv\Scripts\Activate.ps1
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# ⚙️ Configuration

Create your configuration file according to the project's configuration system.

Example:

```yaml
openai:
  api_key: "YOUR_API_KEY"
  base_url: "https://api.example.com/v1"
```

Do not commit credentials.

---

# ▶️ Basic Usage

The main entry point is:

```bash
python -m app.main
```

A complete example:

```bash
python -m app.main ^
  --input "C:\Books\book.epub" ^
  --output "C:\Books" ^
  --from-lang FA ^
  --to-lang EN ^
  --model gpt-5.6-terra
```

PowerShell:

```powershell
python -m app.main `
  --input "C:\Books\book.epub" `
  --output "C:\Books" `
  --from-lang FA `
  --to-lang EN `
  --model gpt-5.6-terra
```

---

# 📚 EPUB Example

```bash
python -m app.main ^
  --input "C:\Books\book.epub" ^
  --output "C:\Books" ^
  --from-lang FA ^
  --to-lang EN ^
  --model gpt-5.6-terra
```

The application will:

```text
1. Load configuration
2. Create API client
3. Detect EPUB
4. Build chunks
5. Save chunks
6. Translate chunks
7. Save every successful translation
8. Reassemble EPUB
9. Save output
10. Cleanup temporary files
```

---

# ▶️ Resume Example

If the process stops:

```bash
python -m app.main ^
  --input "C:\Books\book.epub" ^
  --output "C:\Books" ^
  --from-lang FA ^
  --to-lang EN ^
  --model gpt-5.6-terra ^
  --mode resume
```

---

# 📦 Batch Example

```bash
python -m app.main ^
  --input "C:\Books\book.epub" ^
  --output "C:\Books" ^
  --from-lang FA ^
  --to-lang EN ^
  --model gpt-5.6-terra ^
  --mode batch
```

Check the batch later:

```bash
python -m app.main ^
  --input "C:\Books\book.epub" ^
  --output "C:\Books" ^
  --from-lang FA ^
  --to-lang EN ^
  --model gpt-5.6-terra ^
  --mode batchcheck
```

---

# 🧪 Development Test

Run the project in test mode:

```bash
python -m app.main ^
  --input "C:\Books\book.epub" ^
  --output "C:\Books" ^
  --from-lang FA ^
  --to-lang EN ^
  --mode test
```

This avoids unnecessary API requests when testing the document pipeline.

---

# 🛠️ Error Handling

The application distinguishes between temporary and permanent API errors.

## Temporary Errors

Examples:

```text
429
500
502
503
504
```

These are retried automatically.

---

## Permanent Errors

Examples:

```text
404 model_not_found
Invalid API key
Invalid request
Unsupported model
```

These are not endlessly retried.

For example:

```text
404 model_not_found
```

usually indicates that the requested model is not available through the configured API provider.

---

# ❗ Model Availability

Model names are provider-specific.

For example:

```text
gpt-5.6-terra
```

may be available through a specific OpenAI-compatible provider, while:

```text
gpt-5.6
```

or:

```text
gapgpt-qwen-3.5
```

may not be available through that provider.

Therefore, a model name should always be verified against the configured API provider.

A successful API connection does **not** necessarily mean every model is available.

---

# 🔍 Troubleshooting

## API returns 404 model_not_found

Example:

```text
Error code: 404
model_not_found
```

Check:

```text
1. Model name
2. API provider
3. Base URL
4. Provider model availability
```

---

## API returns 503

Example:

```text
Error code: 503
request failed
```

This generally indicates a temporary provider-side failure.

The application automatically retries the request.

If the service remains unavailable:

```text
Ctrl+C
```

can safely stop the process.

Then retry later with:

```bash
--mode resume
```

---

## Translation stops unexpectedly

Check the temporary job directory:

```text
temp/
```

The application saves translations after every successful chunk.

Run:

```bash
--mode resume
```

to continue.

---

## Progress log warning

If you see:

```text
Warning: Could not write progress log: 'log_file'
```

the translation pipeline itself may still work, but the logging configuration needs to be checked.

Inspect:

```text
app/core/logging.py
```

and:

```text
app/jobs/state.py
```

---

# 📁 Important Files

## `app/main.py`

Application entry point.

Responsible for:

- CLI arguments
- Configuration loading
- API client initialization
- Starting the translation pipeline

---

## `app/pipeline/pipeline.py`

Main orchestration layer.

Responsible for:

- Job initialization
- Resume handling
- EPUB/PDF routing
- Translation orchestration
- Final reconstruction
- Cleanup

---

## `app/translation/translator.py`

Core translation engine.

Responsible for:

- Translating individual chunks
- Retry logic
- Fast mode
- Resume mode
- Batch mode
- Test mode
- Saving translations

---

## `app/translation/prompts.py`

Translation prompt definitions.

Responsible for constructing system prompts based on:

```text
source language
target language
file type
```

---

## `app/translation/batch.py`

Batch processing functionality.

Responsible for:

- Creating batch requests
- Checking batch state
- Retrieving batch output
- Parsing batch responses

---

## `app/jobs/state.py`

Job persistence.

Responsible for:

- Saving chunks
- Saving translations
- Loading job state
- Creating temporary job structures

---

## `app/jobs/manager.py`

Job management.

Responsible for finding resumable jobs.

---

## `app/jobs/cleanup.py`

Temporary file and API resource cleanup.

---

## `app/core/paths.py`

Centralized path and job ID handling.

---

## `app/core/logging.py`

Application progress logging.

---

# 🧱 Design Principles

The project follows several important design principles.

### Separation of Responsibilities

Translation logic should not be mixed with:

```text
CLI
File handling
Job state
Logging
Cleanup
Prompt construction
```

Each responsibility has its own module.

---

### Save Early, Save Often

Translation results are saved immediately after successful API responses.

```text
API success
    ↓
translation memory
    ↓
save_translations()
```

This significantly improves reliability for long-running jobs.

---

### Fail Safely

A temporary API error should not destroy the entire job.

The system:

```text
retry
 ↓
save successful progress
 ↓
allow interruption
 ↓
resume later
```

---

# 🔮 Future Improvements

Potential future improvements include:

- [ ] Web-based frontend
- [ ] Real-time translation progress
- [ ] Job dashboard
- [ ] Background workers
- [ ] Queue-based processing
- [ ] Redis/Celery integration
- [ ] Database-backed job state
- [ ] Multi-user job management
- [ ] Streaming translation output
- [ ] Automatic model fallback
- [ ] Provider fallback
- [ ] Translation quality evaluation
- [ ] Glossary support
- [ ] Custom terminology
- [ ] Translation memory
- [ ] OCR optimization for scanned PDFs
- [ ] Better HTML preservation
- [ ] Parallel chunk translation
- [ ] Cost estimation
- [ ] Token usage tracking
- [ ] API usage statistics
- [ ] Web deployment

---

# 🔐 Security Notes

Never commit:

```text
API keys
Passwords
Tokens
Private configuration
Personal documents
Translated books
Temporary job files
```

Recommended `.gitignore` entries:

```gitignore
.venv/
__pycache__/
*.pyc

.env
config.yaml

temp/
data/

*.log

translations.json
```

If a secret is accidentally committed to Git:

1. Revoke the secret immediately.
2. Generate a new key.
3. Remove the secret from the repository history.
4. Update the local configuration.

---

# 🧪 Recommended Development Workflow

When developing a new feature:

```text
1. Test with a small EPUB
        ↓
2. Use test mode
        ↓
3. Test one or two chunks
        ↓
4. Test fast mode
        ↓
5. Test Ctrl+C
        ↓
6. Test resume
        ↓
7. Test batch mode
        ↓
8. Test final EPUB reconstruction
        ↓
9. Test cleanup
```

This avoids wasting API credits during development.

---

# 📌 Example Translation Session

A normal translation session may look like:

```text
============================================================
J Book Translate
============================================================

Input    : C:\Books\book.epub
Output   : C:\Books
From     : FA
To       : EN
Model    : gpt-5.6-terra
Mode     : None

============================================================

File type: epub

Starting new job:
book_FA_EN_gpt-5.6-terra_20260818_120005

Total chunks to process: 48

Processing mode: fast

Translating 48 chunks in 'fast' mode

============================================================

Translating chunk 1/48
Chunk ID: chunk-0
Completed: 0/48

============================================================

API request for chunk chunk-0

Chunk chunk-0 translated successfully.

Saved progress:
1/48 chunks

...

Chunk chunk-47 translated successfully.

Saved progress:
48/48 chunks

============================================================

Translated EPUB saved successfully.

Processing completed successfully.
============================================================
```

---

# 🏁 Project Status

J Book Translate currently provides the foundation for a modular book translation system with:

```text
EPUB processing
       +
PDF processing
       +
Chunking
       +
OpenAI-compatible APIs
       +
Retry handling
       +
Persistent state
       +
Resume
       +
Batch processing
       +
Output reconstruction
```

The architecture is designed to evolve from a local CLI application into a larger translation platform with a web interface and background job processing.

---

# 📜 License

Add your preferred license here.

Example:

```text
MIT License
```

---

# 👨‍💻 Development

This project is under active development.

The architecture is intentionally modular so that individual components can be improved without rewriting the entire application.

Main areas of development:

```text
Translation Engine
       │
       ├── Provider Integration
       ├── Retry System
       ├── Batch Processing
       └── Translation Quality
       
Document Pipeline
       │
       ├── EPUB
       ├── PDF
       ├── OCR
       └── Reconstruction
       
Job System
       │
       ├── State
       ├── Resume
       ├── Progress
       └── Cleanup
       
Future Web Platform
       │
       ├── API
       ├── Frontend
       ├── Authentication
       └── Real-time Progress
```

