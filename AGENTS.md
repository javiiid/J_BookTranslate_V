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

- **Translation runs through a calibration workshop.** `/workspace` is intake only: it stores the upload and opens `/api/calibrations`. The reader settles voice, glossary, models and budget on 1–3 real samples, seals the profile, and only then does the full book run. So picking a file costs nothing, and this page has no queue, no `POST /api/jobs`, and no tone/style picker — the workshop owns those. The estimate dialog on `/workspace` is the **rescue** path only (a rescue is already-priced remainder work). `srt` and `quality_report` are rejected in a calibration session, so they are not offered.
- **`/api/jobs/upload` returns `file_path`, not `upload_id`.** `POST /api/calibrations` wants a bare filename — it joins it to the upload dir itself and rejects any separator, so the browser must not choose a server path. Use `withUploadId()` / `uploadIdFrom()` from `lib/api.ts`; do not slice paths at a call site.
- **A lib module that a test imports must use `./x.ts`,** not `./x`. `node --test` strips types but resolves nothing: extensionless fails with `ERR_MODULE_NOT_FOUND` and takes the whole file — and its decisions — out of the suite. (`chunks.ts`, `terms.ts`, `calibration.ts` do this.)
- **The product name is کالیما**, never کالیوا. `tests/brand-name.test.ts` holds it: valid UTF-8 containing the wrong letters passes mojibake checks, `tsc`, the linter and the contrast audit, so only a check on the letters finds it.
- **Theme key `jbook-study-dark`** (`src/hooks/useTheme.ts`) is shared with Python pages. Don't rename or user themes silently reset.
- `sanitize_html` stays Python. Chapter HTML arrives sanitised; render with `dangerouslySetInnerHTML`, never re-sanitise in TS (security tests live in Python `tests/test_reader_images.py`).
- `src/styles/tokens.css` is the only colour/type source. No hex or Tailwind colour classes in components — add a semantic token first. Python's `design-system/` is a separate older system; never auto-sync them.
- `ROW_H = 96` in `src/lib/virtual.ts` must equal the `height` in `tokens.css` and `ROW_H = 96, OVERSCAN = 6` in Python `app/jobs/detail_page.py`, or rows overlap and the scrollbar lies.
- Term normalisation: TS and Python both **keep** ZWNJ, soft hyphen, bidi controls. JS once stripped ZWNJ that Python kept → duplicate glossary terms. The probe covers 19 awkward inputs; keep it green.
- Fonts come from this origin, not Google Fonts. `docs/build_fonts.py` copies woff2 from the Python repo into `public/fonts/` + `src/styles/fonts.generated.css` (both gitignored — Python owns binaries). Don't base64-inline fonts (29 KB → 370 KB CSS, uncacheable). Brand SVGs in `public/brand/` are two files, not `currentColor` inversions — hues change roles per theme.
- Type floor 12 px (`--text-caption`), line-height ≥ 1.6 for running text — Persian joining breaks below that. `label`/`button` sharing 13 px is the one allowed repeat. `tokens.contrast.test.ts` enforces 144 WCAG 2.2 AA pairs; audit scripts read `scripts/page-data.json` + `scripts/preview/` (both gitignored user data).
- `/reader` is proxied to the **Python** reader until the React port gains pairing/glossary/settings (`vite.config.ts`, `tests/routing.test.ts` holds the exception). Doubled chapter titles (`stripDuplicatedHeading`/`stripLeadingTitle` in `src/lib/chunks.ts`) are a Python-side defect — fix in `app/`, not here.
- **Theme: `useTheme` follows the OS until the reader presses the toggle.** `localStorage['jbook-study-dark']` is `'1'`/`'0'`, and **absent is not the same as `'0'`** — absent means "follow `prefers-color-scheme`", `'0'` means "I chose light even though my phone is dark". Collapsing them (reading anything that is not `'1'` as light) is what made the app come up white on a dark-mode phone. The toggle is in the desktop rail footer *and* in the mobile bar's chrome slot (a sibling of the `<ul>`, never a sixth `MOBILE_NAV` entry), plus a panel on `/account`.
- **`min-w-0` on any grid/flex item holding user text.** A grid item defaults to `min-width: auto` = "never smaller than my widest content", so a real 150-character filename widened the whole page to 1,608px on a 390px phone. `minmax(0,1fr)` bounds the *track* only — the item inside still refuses to shrink until told. Measure it in a browser after touching a list that shows names; no source-level rule catches this.
- **`truncate` in an RTL line cuts the wrong end.** The ellipsis goes at the *containing block's* inline end, so a long Latin filename showed its tail and lost the part that identifies the book. Put `dir="ltr"` on the truncating element itself (plus `text-right` to keep it against its badge). A `<bdi>` isolate does **not** help — it reorders the text and leaves the ellipsis where it was.
- `job.reader` is a backend path (`/reader/<id>`): link it with `<a href>`, never `<Link to>` — the router would intercept it and render the handover placeholder. Same reason bare `/reader` is a dead end: don't link to it (landing/404 go to `/library`). Two cards may point at one destination there — key the list on `title`, not `to`, or React drops one for duplicate keys.
- **Viewport height is owned once, in `tokens.css` `body`.** `dvh` re-resolves when the mobile browser bar slides, so stacking `min-h-dvh` on the shell made the page grow while you scrolled down it — "I reach the end and there's more empty page". `AppShell` grows with its content.
- Workspace uploads twice (POST `/api/jobs/upload` for the estimate, then POST `/api/jobs` with the File again): localhost-cheap but orphans one temp file per run. The backend comment promises an `upload_token` lookup, but POST `/api/jobs` never implemented it — needs a backend change, not a frontend one. (The calibration path does not have this problem: it never re-uploads.)
- PUT `/api/reader/settings` takes a FLAT partial (`{reading_font_size: 20}`); `{value: {...}}` returns `ok:true` while saving nothing. POST `/api/provider-config/test` returns `{message, base_url, models: <count>, selected_model, model_available}` — `models` is a number, not a list.
- `request()` in `lib/api.ts` throws `ApiError` (with status) even for non-JSON proxy pages — never let a raw `SyntaxError` reach a page. `badgeClass`/`statusLabel` in `lib/format.ts` fall back for unknown future statuses.
- Mojibake is invisible to tsc/lint/diff/contrast audit (valid UTF-8 + valid TSX, wrong glyphs). `tests/encoding.test.ts` rejects Latin-1 signatures and asserts real Persian remains; repair with `docs/fix_mojibake.py` (cp1252 with latin-1 fallback, writes only if unambiguously better).
- Phase 6 (serve `dist/` from Python, delete old templates) is **not started** and irreversible — needs `app/web.py` changes (otherwise frozen). Run `docs/audit_bundle.py` before deciding.
