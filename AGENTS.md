# KALIMA backend — agent guide

Python EPUB/PDF translator. Local-only: server binds `127.0.0.1:8765`, OpenAI-compatible API, thread-based concurrency, resumable on-disk jobs. `app/main.py` is CLI entry, `app/web.py` is web/API server. Full product spec in `readme.md`; this file is only what agents get wrong.

## Setup & commands

- `python -m venv .venv` + `.\.venv\Scripts\Activate.ps1` + `pip install -r requirements.txt` (openai, PyYAML, PyMuPDF, pypandoc_binary, fonttools, playwright).
- `python -m app.web` → http://127.0.0.1:8765. `python -m app.main --help` for CLI.
- `config/config.yaml` is the only config source. Create manually (see `readme.md` sample); never commit it — gitignore uses a **named** rule, not `*.yaml`, so future workflow/packaging YAML isn't silently dropped.
- Saving from `/account` rewrites `config.yaml` with `yaml.safe_dump` and **strips comments**. Values survive, explanations don't.
- Model default comes from `resolve_default_model()` reading `config.yaml`. Never hardcode a model; empty model field = configured default. Unknown model → `400`, not silent fallback.

## Test

- `python -m pytest -q` (full suite, ~291 tests). Single module: `python -m pytest tests/test_library.py -q`.
- **Stop `python -m app.web` before testing.** It holds the SQLite lock → ~53 spurious failures.
- If system temp is restricted: `python -m pytest -q -p no:cacheprovider --basetemp .test-tmp\full`.
- `pytest.ini` only sets `pythonpath=. testpaths=tests`. No formatter/linter/typecheck enforced — match nearby code (4-space, `snake_case` funcs, `PascalCase` classes).

## Architecture facts that matter

- Thread-based parallelism (`max_concurrency: 12`, hard cap in `app/core/config.py`), **not asyncio** — deliberate, preserves commit order + stop/resume. `app/core/rate_limit.py` (`AdaptiveRateLimiter`): halves ceiling on `429`, honors `Retry-After`, stoppable via `stop_event`.
- `Ctrl+C` at concurrency 12 can waste up to 12 paid requests (finished but uncommitted). Nothing is ever mis-marked complete; resume is always safe.
- Glossary is snapshotted at job start so chunk 1 uses the same terms as chunk 300. `glossary_mode: off` (default) | `deferred` (+1 LLM call/chunk after) | `inline` (+1/chunk, forces sequential). Proposal = 12 sampled chunks → 1 LLM call → user ticks approves; server-side filter drops terms not literally in the sampled text. Never auto-add during translation.
- Runtime dirs `data/`, `temp/`, `/output/` are gitignored and never committed (one PDF export hit 99 MB). Leading slash in `/output/` is load-bearing: bare `output/` would also swallow source `app/output/` (format modules). Verify: `git check-ignore -v app/output/convert.py` must print nothing.
- Security: `Host` checked on **all** methods (DNS-rebinding), `Origin`/`Sec-Fetch-Site` on mutating methods, bind loopback only. Reader images served as local assets, never inline HTML: strip `onerror`/`onload`/`<base>`/`javascript:`/`data:`/remote `src`; SVG with `sandbox` + `nosniff`. `sanitize_html` stays Python-side — the React UI must not re-implement it.

## Known-broken (don't "fix" by adding one string)

- `--mode pdfbilingual` is offered in `app/cli/parser.py` + web form but rejected in `translator.py` (`ValueError`). Needs a product decision, not a set addition.
- SRT output is generated but untranslated content. Non-UTF-8 EPUB chapters silently skipped. PDF vision prompt hardcoded DE→EN in `pdf_handler.py`. No OCR / `get_text()` fast path — every PDF renders as image. `load_batch_state` picks newest `batch_status_*.json` by mtime with no book filter (cross-book state bleed).

## Commits

Conventional-style subjects (`feat: …`, `chore: …`), one logical change. PRs: behavior + validation commands + issue link + screenshots for dashboard/library/reader changes. Never commit keys, books, job state, `.venv/`.
