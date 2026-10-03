# KALIMA UI — agent guide

React port of the Python app at `D:\J_BookTranslate_V`. **Python is single source of truth — port, don't reimplement.** When they disagree, the Python page is correct. Full rationale in `README.md`; this file is only what agents get wrong.

## Run

Both processes must run:

```powershell
# backend (from the Python repo)
.\.venv\Scripts\python.exe -m app.web      # http://127.0.0.1:8765
# this UI (from ui/)
npm install
npm run dev                                # http://localhost:5173
```

Vite proxies only `/api`, `/downloads`, `/reader` to the backend — no CORS anywhere. Backend address: `KALIMA_API`, legacy `JBT_API` fallback, default `http://127.0.0.1:8765`.

## Commands (from `ui/`)

- `npm run dev` / `npm run build` — both run `ensure-fonts.mjs` + `check-brand.mjs` guards first; they fail with the fixing command, not a cryptic error.
- `npm run typecheck` = `tsc -b --force`. Never `npx tsc --noEmit`: root `tsconfig.json` is solution-style (`files: []`), so `--noEmit` checks nothing and exits 0 — this hid 4 errors before.
- `npm run verify` = typecheck → lint (`oxlint`) → tests. `npm test` = `node --test tests/*.test.ts`.
- `npm run check:api` asserts live backend vs TS types (re-capture `docs/inventory/` before changing a type). `npm run check:normalisation` diffs TS/Python term-key functions. `npm run audit:contrast` builds real components and checks 622 elements in both themes.

## Rules that must not drift

- Theme key `jbook-study-dark` (`src/hooks/useTheme.ts`) is shared with Python pages. Don't rename or user themes silently reset.
- `sanitize_html` stays Python. Chapter HTML arrives sanitised; render with `dangerouslySetInnerHTML`, never re-sanitise in TS (security tests live in Python `tests/test_reader_images.py`).
- `src/styles/tokens.css` is the only colour/type source. No hex or Tailwind colour classes in components — add a semantic token first. Python's `design-system/` is a separate older system; never auto-sync them.
- `ROW_H = 96` in `src/lib/virtual.ts` must equal the `height` in `tokens.css` and `ROW_H = 96, OVERSCAN = 6` in Python `app/jobs/detail_page.py`, or rows overlap and the scrollbar lies.
- Term normalisation: TS and Python both **keep** ZWNJ, soft hyphen, bidi controls. JS once stripped ZWNJ that Python kept → duplicate glossary terms. The probe covers 19 awkward inputs; keep it green.
- Fonts come from this origin, not Google Fonts. `docs/build_fonts.py` copies woff2 from the Python repo into `public/fonts/` + `src/styles/fonts.generated.css` (both gitignored — Python owns binaries). Don't base64-inline fonts (29 KB → 370 KB CSS, uncacheable). Brand SVGs in `public/brand/` are two files, not `currentColor` inversions — hues change roles per theme.
- Type floor 12 px (`--text-caption`), line-height ≥ 1.6 for running text — Persian joining breaks below that. `label`/`button` sharing 13 px is the one allowed repeat. `tokens.contrast.test.ts` enforces 144 WCAG 2.2 AA pairs; audit scripts read `scripts/page-data.json` + `scripts/preview/` (both gitignored user data).
- `/reader` is proxied to the **Python** reader until the React port gains pairing/glossary/settings (`vite.config.ts`, `tests/routing.test.ts` holds the exception). Doubled chapter titles (`stripDuplicatedHeading`/`stripLeadingTitle` in `src/lib/chunks.ts`) are a Python-side defect — fix in `app/`, not here.
- Mojibake is invisible to tsc/lint/diff/contrast audit (valid UTF-8 + valid TSX, wrong glyphs). `tests/encoding.test.ts` rejects Latin-1 signatures and asserts real Persian remains; repair with `docs/fix_mojibake.py` (cp1252 with latin-1 fallback, writes only if unambiguously better).
- Phase 6 (serve `dist/` from Python, delete old templates) is **not started** and irreversible — needs `app/web.py` changes (otherwise frozen). Run `docs/audit_bundle.py` before deciding.
