<div align="center">

# 📖 KALIMA

**Translate EPUB and PDF books with any OpenAI-compatible API — chunked, resumable, with a human-approved glossary.**

Translation is split into small chunks, progress persists on disk, and work
resumes exactly where it stopped — even after a reboot.

> 🚀 **Product direction: hosted launch.** The current build still runs locally
> (see Quick start); the launch plan — multi-user accounts, server-side billing,
> production deployment — lives in [`LAUNCH.md`](LAUNCH.md).

**[فارسی](README_FA.md)** · Persian readers: the full original documentation lives in `README_FA.md`.

<p>
  <img src="app/brand/kalima-mark-light.svg" width="88" alt="KALIMA mark">
</p>

<br>

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-635%20passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Launch](https://img.shields.io/badge/launch-in_progress-yellow.svg)](LAUNCH.md)

<br>

**11× faster** · **12 concurrent chunks** · **pre-translation glossary** · **calibration workshop** · **~17K lines of Python**

</div>

---

## 📑 Contents

- [Why this project is different](#-why-this-project-is-different)
- [Features](#-features)
- [Quick start](#-quick-start)
- [Glossary flow](#-glossary-flow)
- [Calibration workshop](#-calibration-workshop)
- [Estimate & rescue](#-estimate--rescue)
- [Performance & concurrency](#-performance--concurrency)
- [Project architecture](#-project-architecture)
- [Configuration](#-configuration)
- [Web interface](#-web-interface)
- [Command line](#-command-line)
- [Output formats](#-output-formats)
- [Model selection](#-model-selection)
- [Security](#-security)
- [Testing](#-testing)
- [Development](#-development)
- [Open issues](#-open-issues)
- [Launch plan (hosted)](LAUNCH.md)

---

## 💡 Why this project is different

Most book-translation tools send the whole book in one request, learn
terminology without asking you, or lose everything when work stops halfway.
These three problems drive every decision in this project:

### 1. Your book stays in your workspace

Your files live in your own workspace and are processed only by the model
provider you chose — never shared, never used for training. (The current build
runs on your own machine at `127.0.0.1` with the API key in a gitignored file;
the hosted launch keeps the same promise per user — see `LAUNCH.md`.)

### 2. Many chunks go up at once

The bottleneck was network I/O, not CPU. So translation is **thread-based**, not `async`:

| Workers | Time for 12 chunks | Speedup |
| --- | --- | --- |
| Sequential | 72.2 s | 1.0× |
| 3 | 24.2 s | 2.99× |
| 6 | 12.3 s | 5.86× |
| **12** | **6.6 s** | **10.90×** |

API request count stayed **flat at 24** in every mode — only time shrank.

An `asyncio` rewrite was deliberately rejected: it added nothing for the user
and would have lost commit ordering and stop/resume.

### 3. Half-finished work is never lost

Every chunk writes its result to disk. `Ctrl+C`, a dead laptop battery, or a
crash means "resume from the last healthy spot", not "start from zero".

---

## ✨ Features

| | Feature | Notes |
| --- | --- | --- |
| 📚 | **EPUB and PDF** | Both formats, with a built-in reader |
| 🧪 | **Calibration workshop** | Settle voice, glossary, model and budget on 1–3 real samples before the full run |
| 💰 | **Honest cost estimate** | Real chunk counts, script-aware token estimates, concurrency-aware timing |
| 🛟 | **Rescue & re-import** | Export a rescue archive, re-import it later without re-paying for done chunks |
| ⚡ | **12 concurrent chunks** | With adaptive rate limiting |
| 🔁 | **Stop and resume** | Even after the computer shuts down |
| 🧠 | **Proposed glossary** | The model proposes, **you** approve |
| 🛡️ | **No auto-learning** | Nothing is added to the glossary mid-translation |
| 🧩 | **Semantic chunker** | Lossless, tag-aware, token-budgeted splits with context window |
| 📊 | **Translation monitor** | Five tabs: summary, chunks, QA, log, files |
| ✅ | **Quality scorer** | Six-dimension chunk QA, opt-in via `quality_report` |
| 🖼️ | **Images in the reader** | Full asset/text separation |
| 🗂️ | **Local library** | With search, covers, and archive |
| 🔑 | **Auth** | Password + OTP email + Google/Apple OAuth, throttled |
| ❓ | **Help center** | Searchable articles and FAQ in Persian and English |
| 🖥️ | **React frontend** | Strict-TypeScript UI served locally on :5173 |
| 🌙 | **Night reading mode** | OLED theme for long sessions |
| 🇮🇷 | **Persian RTL interface** | Local fonts, no CDN dependency |
| 📤 | **9 output formats** | From DOCX to SRT and QA reports, with embedded Vazirmatn + RTL |
| 🔒 | **CSRF protection** | Rejects requests from foreign pages |

---

## 🚀 Quick start

The project runs as **two processes**: the Python backend first, then the
React frontend. Keep both running and use the app locally in your browser.

### Prerequisites

- Python 3.11 or newer (tested on 3.14)
- Node.js 18+ (for the frontend only)

### Step 1 — Install the backend

From the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

This installs `openai`, `PyYAML`, `PyMuPDF`, `pypandoc_binary`, `fonttools`
and `playwright`.

<br>

### Step 2 — Create `config/config.yaml`

Create the file **`config/config.yaml`** (repo root → `config` folder → file
`config.yaml`). There is no example file to copy — write it manually:

```yaml
openai:
  api_key: "YOUR_API_KEY"
  base_url: "https://api.example.com/v1"

translation:
  default_model: "gpt-5.6-luna"
  default_from_lang: "EN"
  default_to_lang: "FA"
```

- `openai.api_key` / `openai.base_url` point at any OpenAI-compatible API.
- `translation.*` holds the defaults (model, languages, concurrency, glossary
  mode…). The full key table is under [Configuration](#-configuration).
- The `/account` page can rewrite this file later (`yaml.safe_dump`).

> 🔐 `config/config.yaml` is gitignored (named rule) and **never** committed.

<br>

### Step 3 — Start the backend

```powershell
python -m app.web
```

It listens loopback-only at **http://127.0.0.1:8765**. Leave this terminal
running — the frontend needs it.

<br>

### Step 4 — Start the frontend

In a **second** terminal:

```powershell
cd frontend/ui
npm install
npm run dev
```

This serves the React UI at **http://localhost:5173**. `npm run dev` first runs
two guards (`ensure-fonts`, `check-brand`) that fail with the fixing command if
fonts or brand assets are missing.

Vite proxies `/api`, `/downloads`, `/covers` and `/reader` to the backend, so
the browser sees a single origin — no CORS anywhere. If your backend is not on
port 8765, point the UI at it with the `KALIMA_API` environment variable
(legacy name `JBT_API` still works):

```powershell
$env:KALIMA_API = "http://127.0.0.1:8765"
npm run dev
```

<br>

### Step 5 — Open it locally

| What | Address |
| --- | --- |
| Full app (React UI) | **http://localhost:5173** |
| Backend alone (Python pages + API) | **http://127.0.0.1:8765** |

Open the React UI, drop an EPUB or PDF file on `/workspace`, and calibrate on
1–3 samples before the full run. That's the whole flow.

> Python is the single source of truth: the React app in `frontend/ui` is a
> port, not a second implementation. `/reader` is still proxied to the Python
> reader until the React port is complete.

<br>

<details>
<summary><b>Translate without the web UI (command line)</b></summary>

```powershell
# Regular translation
python -m app.main --input ".\books\source.epub" --from-lang EN --to-lang FA

# Resume a half-finished translation
python -m app.main --input ".\books\source.epub" --from-lang EN --to-lang FA --mode resume

# Several outputs at once
python -m app.main --input ".\books\source.epub" --outputs markdown,docx,quality_report

# Custom translation style
python -m app.main --input ".\books\source.epub" --style technical
```

</details>

---

## 🧠 Glossary flow

Propose, review, approve — in that order.

This is the project's most important architectural change.

### Why auto-learning was removed

The old approach: after translating each chunk, ask the model "did you see any
new terms?" and add the answer to the glossary. The problem was that it
**conflicted with speed**.

By the time one chunk's prompt is ready, a term learned from a still-translating
chunk is already too late — that chunk was sent earlier. Fixing this would have
required sequential translation, killing the entire 10.90× speedup.

### The fix: learn, but **before** translating

```text
 1. You upload the book
 2. You press "Propose glossary"
        ↓
    12 chunks sampled across the book → 1 LLM request
        ↓
 3. Review table: tick, edit, or reject
        ↓
 4. "Approve selected" → only those enter the glossary
        ↓
 5. Translation with 12 workers
        ↓
 6. Done. Nothing was added automatically.
```

**Key result:** because the glossary is snapshotted at job start, **every chunk —
including chunk 1 — translates with the same glossary.** That was not true before.

### What does it save?

| | Glossary API calls | Chunk coverage |
| --- | --- | --- |
| Before | **300** calls for a 300-chunk book | 0% |
| Now | **1** call | **100%** |

### Anti-hallucination guard

Every term the model proposes must **literally occur in the text it was shown**.
If the model invents a name, it is discarded.

This guard is server-side and applies regardless of what the model says, because
a hallucinated glossary would poison every later translation of that book.

### What if you skip the proposal?

You see a warning and **can continue** — without a glossary, just with
non-unified terminology.

### Behavior setting

`glossary_mode` in `config/config.yaml`:

| Value | Behavior |
| --- | --- |
| `off` *(default)* | No learning. Only the approved glossary. |
| `deferred` | Automatic learning after all chunks finish. |
| `inline` | Learning between chunks. Forces sequential translation. |

> `deferred` and `inline` each add **one LLM request per chunk**.
> That is why `off` is the default.

---

## 🧪 Calibration workshop

Translation runs through a calibration workshop. `/workspace` is intake only:
it stores the upload and opens a calibration session. The reader settles voice,
glossary, model and budget on 1–3 real samples, seals the profile, and only then
does the full book run.

```text
 1. Upload the book (costs nothing — intake only)
        ↓
 2. Calibration session on 1–3 real samples
    · tone preset (literary, academic, modern, …)
    · glossary terms reviewed and approved
    · model for samples + model for the full run
    · optional fallback model: a cheaper model that serves a chunk only
      after the primary exhausts all retries (must be supported and cheaper)
    · budget guard: sealed spending limit
        ↓
 3. Seal the profile → full book runs with the locked profile
```

Rules worth knowing:

- Picking a file costs nothing; the workshop owns tone/style choices, so the
  intake page has no queue and no tone picker.
- The estimate dialog on `/workspace` is the **rescue** path only (already-priced
  remainder work) — see below.
- `srt` and `quality_report` are rejected inside a calibration session and must
  be requested as separate outputs.
- Reopening the same book with the same configuration keeps drafts, approvals
  and spending — calibration state survives restarts, and an interrupted run is
  marked honestly instead of silently retried.
- Fallback chunks are always marked: the job log and `fallback.json` in the job
  directory record which chunks the fallback model served. Without a configured
  fallback, exhaustion fails exactly as before.

API: `/api/calibrations`, `/api/calibration-operations/*`.

---

## 💰 Estimate & rescue

### Honest estimates

The old estimate divided file size by 12,000, ignored concurrency, and reported
cost as a hardcoded `0.0` — next to a "start translating" button, a zero reads
as "free", not "unknown".

`app/jobs/estimate.py` computes the real numbers instead:

- **Real chunk counts** from the semantic chunker, not from file size.
- **Script-aware token estimates** — Arabic script prices at roughly two
  characters per token instead of one Latin average (deliberately biased high:
  an undercount understates the bill).
- **Concurrency-aware timing** at `max_concurrency = 12`.
- **Per-model pricing** for the project's actual models.

### Rescue archives

`POST /api/jobs/{id}/rescue` produces a `*_rescue.zip` carrying the translated
text, chunk list, glossary snapshot and settings. Unlike a dead backup, it can
be **re-imported**: the job returns to a resumable state rebuilt from the
archive, so already-translated chunks are not paid for twice. The estimate
dialog is the rescue path for that already-priced remainder work.

---

## ⚡ Performance & concurrency

### Why threads and not asyncio

The bottleneck was waiting on the network. The `openai` library is synchronous.
An `asyncio` rewrite had real costs (complexity, lost commit ordering and
stop/resume) and added nothing.

### `AdaptiveRateLimiter`

`app/core/rate_limit.py` — a sliding window plus a minimum gap between requests:

- Halves the ceiling on every `429` response
- Honors `Retry-After`
- Climbs back up slowly when things improve
- Stoppable via `stop_event`, so stopping is instant

### A conscious tradeoff

At concurrency 12, pressing `Ctrl+C` can waste up to **12 paid requests**
(requests finished but results not committed).

**Nothing is ever wrongly marked "complete"**, and resuming always works
correctly. This is a deliberate tradeoff, not a hidden bug.

---

## 🏗 Project architecture

Each package is independent with one responsibility.

```text
app/
├── main.py          CLI entry point
├── web.py           HTTP server + guards (60+ /api/* routes)
│
├── calibration/     sample workshop (service, engine, store, routes)
│   ├── service.py       sessions, approvals, budget, guarded execution
│   ├── engine.py        tone presets, token/cost math
│   └── store.py         persistent session/operation state
│
├── pipeline/        EPUB & PDF processing
│   ├── pipeline.py      main coordinator
│   ├── semantic_chunker.py  lossless, token-budgeted chunking
│   ├── pdf_handler.py   PDF rendering & extraction
│   └── quality_scorer.py    6-dimension chunk QA
│
├── output/          output formats (EPUB/DOCX/PDF/Markdown/SRT/…)
│   ├── formats.py       list & registry
│   ├── epub_convert.py  EPUB conversion pipeline
│   ├── rtl_docx.py rtl_pdf.py  RTL output + embedded Vazirmatn
│   └── docx.py  pdf.py  markdown.py  srt.py  …
│
├── translation/     translation engine
│   ├── translator.py    translation loop & concurrency
│   └── prompts.py       prompts
│
├── jobs/            jobs & state
│   ├── state.py         progress persisted on disk
│   ├── estimate.py      honest cost/time estimation
│   ├── rescue.py        rescue export & re-import
│   ├── detail_page.py   translation monitor
│   └── dashboard.py     dashboard
│
├── core/            shared infrastructure
│   ├── config.py        config.yaml reading/writing
│   ├── models.py        supported models
│   ├── rate_limit.py    adaptive limiter
│   └── web_i18n.py      multilingual layer
│
├── reader/          bilingual reader
├── glossary/        glossary (service, proposal, review panel)
├── presets/         translation styles
├── auth/            local password auth & sessions
├── account/         account portal (keys, orders, marketplace)
├── storage/         SQLite database
├── library/         library (search, covers, archive)
├── cli/             command-line parsing
└── welcome/         landing page

frontend/ui/         React port (Vite + strict TS, optional)
tests/               51 files, 635 tests
```

Main code: **~17K lines** of Python.

### Where data goes

```text
data/     database & library metadata
temp/     resumable job state
output/   translated books
```

None of them are in Git. One PDF export alone reached 99 MB, and Git keeps
every blob forever.

> 🚀 At launch these become per-user storage (volumes first, object storage
> later) — see `LAUNCH.md`. New paths go through `app/core/paths.py` only.

---

## ⚙ Configuration

`config/config.yaml` is the only configuration source.

| Key | Default | Purpose |
| --- | --- | --- |
| `openai.api_key` | — | Your API key |
| `openai.base_url` | — | OpenAI-compatible service URL |
| `translation.default_model` | `gpt-5.6-luna` | Default model |
| `translation.default_from_lang` | `FA` | Source language |
| `translation.default_to_lang` | `EN` | Target language |
| `translation.default_mode` | `fast` | Translation mode |
| `translation.max_concurrency` | `12` | Hard cap in `app/core/config.py` |
| `translation.requests_per_minute` | `120` | Request cap; `null` = unlimited |
| `translation.glossary_mode` | `off` | Glossary behavior |
| `translation.temperature` | `0.2` | Output creativity |
| `translation.max_retries` | `5` | Retries |
| `translation.retry_delay` | `5` | Initial retry delay |
| `translation.max_retry_delay` | `60` | Max retry delay |

### Full example

```yaml
openai:
  api_key: "YOUR_API_KEY"
  base_url: "https://api.example.com/v1"

translation:
  default_model: "gpt-5.6-luna"
  default_from_lang: "EN"
  default_to_lang: "FA"
  default_mode: "fast"

  max_concurrency: 12
  requests_per_minute: 120
  glossary_mode: "off"

  temperature: 0.2
  max_retries: 5
  retry_delay: 5
  max_retry_delay: 60
```

> ⚠️ Saving settings from the account page rewrites this file with
> `yaml.safe_dump` and **strips comments**. Values survive, explanations don't.

---

## 🖥 Web interface

The server runs at `http://127.0.0.1:8765`, loopback only.

| Path | What it is |
| --- | --- |
| `/landing` | Landing page |
| `/workspace` | Workspace: upload & monitor (intake — calibration owns the rest) |
| `/workspace/job/{id}` | Single-translation monitor (5 tabs) |
| `/library` | Library (per-user at launch) |
| `/reader/{id}` | Bilingual reader |
| `/account` | Account portal |
| `/help` | Help center (React UI): search, articles, FAQ |

60+ API routes live under `/api/` (jobs, calibrations, library, reader,
glossary, providers, account, analytics, logs, auth, …).

### Translation monitor

`app/jobs/detail_page.py` — five tabs: **summary**, **chunks**, **QA**,
**log**, **files**. The chunk table is windowed so the browser doesn't lock up
on large books.

### Quality reports

The quality scorer (`app/pipeline/quality_scorer.py`) grades every translated
chunk on six dimensions — accuracy 30%, fluency 25%, terminology 15%, format
preservation 15%, boundary integrity 10%, length ratio 5% — in `full`, `light`
or `rules` (no-LLM) mode. It runs only when `quality_report` is requested, in
parallel across chunks, and never breaks the job: failures fall back to
rule-based scores with a flag reason.

---

## 💻 Command line

```text
python -m app.main --input PATH [options]

  --input PATH          EPUB or PDF file
  --output PATH         Output path (optional)
  --from-lang CODE       Source language  (EN, FA, DE, FR)
  --to-lang CODE         Target language
  --model NAME           Translation model
  --mode MODE            resume | test (default: fast)
  --style STYLE          literary | technical | conversational | formal
  --outputs LIST         Extra formats, comma-separated, or all
  --prompt TEXT          Custom prompt
  --debug                Keep temporary files
```

> 🚫 **`--mode pdfbilingual` currently does not work.** It is offered in
> `parser.py` and the web form but is not among the allowed modes in
> `translator.py` and raises `ValueError`. Details under
> [open issues](#-open-issues).

---

## 📤 Output formats

9 formats, via `--outputs` or web checkboxes:

| Format | Notes |
| --- | --- |
| `translated_epub` | Translated EPUB (conversion pipeline) |
| `translated_pdf` | Translated PDF |
| `bilingual_pdf` | Bilingual PDF |
| `docx` | Word, with RTL support |
| `markdown` | Markdown |
| `txt_bilingual` | Bilingual text |
| `json_segments` | Segments as JSON |
| `srt` | Subtitles (books: translated text, estimated timing) |
| `quality_report` | QA report (runs the quality scorer) |

Persian outputs embed **Vazirmatn** fonts and handle RTL in DOCX and PDF
(`rtl_docx.py`, `rtl_pdf.py`).

> 📝 SRT carries the **translated** text. For `.srt` uploads the original
> timecodes are preserved; for books the timing is estimated from the
> translated text at reading speed (~17 chars/sec) in 42-char lines.

---

## 🧩 Model selection

`config.yaml` is the single source of truth. The web form and the pipeline
engine both read from it.

| Model | Notes |
| --- | --- |
| `gpt-5.6-luna` | Main translation model *(default)* |
| `gpt-5.6-terra` | Higher quality |
| `gemini-3.1-flash-lite` | Faster and cheaper |

To switch, change one line in `config/config.yaml`. Form and pipeline move together.

<details>
<summary><b>Why does this section exist?</b></summary>

Six function signatures used to default to `model="gpt-5.6-terra"`. Every call
site that omitted `model` silently sent terra.

The worst case was `transcribe_pdf`, which had **no model parameter at all** —
so every PDF was billed at terra rates even when you had selected luna.

The web dropdown also had a hand-written two-item list whose `selected` option
was baked at write time, so `config.yaml` had no effect on it, and terra was
not in the list at all.

Now `resolve_default_model()` reads from config, and an unknown model is
**never sent to the provider**. Uploading with an unknown model gets a `400`,
instead of failing on the first paid chunk.

</details>

---

## 🔒 Security

### CSRF & DNS-rebinding guards

A local server with an open API and no origin checks can be driven by any web
page the user opens — spending your API credit. CORS does not stop this.

`app/web.py` enforces (current local build):

- `Sec-Fetch-Site` and `Origin` checks on **all** mutating methods
- `Host` checks on **all** methods, including GETs, against DNS rebinding
- Loopback-only binding (`127.0.0.1`)

**Verified with a real attack:** a request that used to return `201 Created`
now returns `403`.

> 🚀 At launch the binding becomes configurable behind a TLS reverse proxy,
> with real CSRF tokens, `Secure` cookies, and login rate-limiting — see
> `LAUNCH.md` Phase A. The loopback-only posture below is the starting point,
> not the target.

### Auth

`app/auth` adds login on top, stdlib only (plus `cryptography` for Apple):
PBKDF2-HMAC-SHA256 (210,000 iterations) for password storage,
`secrets`-generated session tokens of which only the SHA-256 digest touches
the database. Sessions ride an HttpOnly `SameSite=Lax` cookie.

- **Password**: signup/login/logout, change-password (proves the current one,
  kills all other sessions), session list, per-session revoke, revoke-all —
  the leaked-cookie recovery path.
- **Passwordless email**: 6-digit OTP, 10-minute expiry, single-use, hashed
  at rest; log-sender by default, SMTP driver from `config.yaml` when
  configured. First use creates the account.
- **Google / Apple OAuth**: authorization-code flow with one-time state;
  Google verified via tokeninfo over TLS; Apple verified against JWKS (RS256)
  with an ES256 client_secret. Accounts link by provider sub, else by verified
  email. Unconfigured providers fail with an explicit error naming the missing
  `config.yaml` keys — never silently.
- **Abuse throttle**: DB-backed per-email + per-IP failure log with
  progressive rejection on password and OTP endpoints. This retires the old
  loopback-only "no lockout" reasoning (see `LAUNCH.md`).

### Key hygiene

| | Current (local build) | At launch |
| --- | --- | --- |
| Provider key | Only `config/config.yaml` (global) | Server-side, per-workspace; users spend credits, never see keys |
| In Git | **No** — via a named `.gitignore` rule | Same rule; plus secret scanning in CI |
| Past commits | Audited: clean | Re-audit before launch |

> The rule is deliberately **named**, not `*.yaml`. A wildcard could silently
> swallow future CI and packaging files with no warning.

### Reader images

EPUB and PDF images are served as local assets, never inline HTML:

- `onerror`/`onload` handlers and `<base>` tags are stripped
- `javascript:`, `data:` and remote `src` values are rejected
- SVG is served with `Content-Security-Policy: sandbox` and
  `X-Content-Type-Options: nosniff`

---

## 🧪 Testing

```powershell
python -m pytest -q
```

<div align="center">

**635 tests — all passing (51 files)**

</div>

| File | What it guards |
| --- | --- |
| `test_audit_regressions.py` | Every fix of the audit round |
| `test_reader_images.py` | Asset separation & SVG guards |
| `test_model_selection.py` | Single-source model truth |
| `test_glossary_proposal.py` | Sampling & approval rules |
| `test_jobs_detail.py` | Translation monitor |
| `test_estimate.py` / `test_rescue_*.py` | Honest estimates & rescue round-trip |
| `test_semantic_chunker.py` | Lossless chunking invariant |
| `test_quality_scorer.py` | QA scoring |
| `test_outputs.py` | Output formats |

### Running a subset

```powershell
python -m pytest tests/test_model_selection.py -q
```

### If the system temp dir is restricted

```powershell
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp\full
```

> ⚠️ **The server must be stopped.** A running `python -m app.web` holds the
> SQLite lock and produces ~53 spurious failures.

### Frontend tests

```powershell
cd frontend/ui
npm run verify   # typecheck → lint (oxlint) → tests
```

---

## 🛠 Development

The full structure, naming and pull-request rules live in
[`AGENTS.md`](AGENTS.md). The React-side rules live in
[`frontend/AGENTS.md`](frontend/AGENTS.md).

Summary:

- 4 spaces, `snake_case` for functions and variables
- Write the test next to the change, especially for state, resume, glossary
  and the reader
- Conventional-Commits messages
- `data/`, `temp/`, `output/`, keys and generated books are never committed
- **Python is the single source of truth** — the React UI ports, never
  reimplements; when they disagree, the Python page is correct

### Suggested shape of a change

1. Write the smallest test that shows the bug
2. Apply the change
3. Run the narrowest related test
4. Then run the full suite

---

## 📋 Open issues

Honest list of things still not right:

| Issue | Status |
| --- | --- |
| `--mode pdfbilingual` | Offered in `parser.py` and the web form, but not an allowed mode in `translator.py` (`ValueError`). Needs a product decision — not just adding one string to a set. |
| SRT | ✅ Fixed: translated text with estimated timing for books. |
| Non-UTF-8 EPUB chapters | Silently skipped. |
| PDF vision prompt | Hardcoded German→English in `pdf_handler.py`. |
| OCR / `get_text()` fast path | Missing; every PDF renders as an image. |
| Ctrl+C & crash tests | Pinned to 1 worker for hermeticity, so they no longer really exercise concurrency-12 behavior. |
| Serve `dist/` from Python (Phase 6) | Not started and irreversible — needs `app/web.py` changes. |

---

## 📄 License

This project is released under the **MIT License**.

You may use, modify, distribute and sell this software for any purpose
(personal, commercial, educational) — just keep the copyright notice and the
license text in copies.

Full details in [`LICENSE`](LICENSE).

---

<div align="center">

**Made with ❤️ for people who want translated books without uploading them to a stranger's server**

<br>

<sub>
If you see a bug or want to help, open an issue.
Before a PR, please run <code>python -m pytest -q</code>.
</sub>

<sub>Persian documentation: <a href="README_FA.md">README_FA.md</a></sub>

</div>
