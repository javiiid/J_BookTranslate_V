# KALIMA UI

The new React front end for KALIMA.

## Status: un-parked, resuming Phase 2

This was **paused** on purpose. The original trigger was the move from a local
tool to a hosted commercial product, because the local product promises
`pip install` and `python -m app.web` with no build step, and that promise is
worth more than component reuse while the tool runs on the user's own machine.

That trade has since tipped the other way, for a reason worth recording:

- `app/web.py` is 1,461 lines, and the user-facing pages are now large blocks of
  HTML, CSS and JavaScript embedded in Python strings — `detail_page.py`,
  `proposal_page.py`, `account/page.py`, `library/view.py`, `jobs/workspace.py`.
  That is the failure mode the park was meant to avoid, and it has arrived
  anyway, only without the benefit of components.
- A QA review interface and a quality scorer now exist (`quality_scorer.py`).
  That was listed as a resume trigger.

**The rule has not changed: the Python project stays the single source of truth
and this is a port, not a second implementation.** No feature is built here that
does not already exist there. When the two disagree, the Python page is correct.

The `local-first` promise is still the reason this is a *separate* repository
rather than a rewrite: it can be deleted in one `rm -rf` if the trade reverses.

## Why this is a separate repository

The Python project at `D:\J_BookTranslate_V` is **frozen and untouched**. It already
exposes everything as a plain HTTP API under `/api/*`, so the UI needs no shared
code, only a network call. That gives:

- zero regression risk to the 291 Python tests
- the migration can be abandoned by deleting one folder
- `node_modules` never enters the Python repo's history

## Prerequisites

Both processes must run:

```powershell
# 1. backend (existing project)
cd D:\J_BookTranslate_V
.\.venv\Scripts\python.exe -m app.web          # http://127.0.0.1:8765

# 2. this UI
cd D:\J_Translate_Ui\ui
npm install
npm run dev                                     # http://localhost:5173
```

Vite proxies `/api`, `/reader`, `/downloads`, `/library`, `/account`,
`/workspace` to the backend, so there is no CORS setup anywhere.

Override the backend address with `JBT_API` if it is not on port 8765.

## Commands

| Command | Purpose |
|---|---|
| `npm run dev` | dev server with HMR on 5173 |
| `npm run verify` | type-check, then lint, then tests |
| `npm run typecheck` | `tsc -b --force` across app, node and test projects |
| `npm run build` | font and brand guards, type-check, then production build |
| `npm test` | 179 tests (`node --test`, no runner dependency) |
| `npm run check:api` | assert the live backend against the TypeScript types |
| `npm run check:normalisation` | diff the TS and Python term-key functions |
| `npm run preview` | serve the built bundle |

`npm run dev` and `npm run build` both run two guards first:
`ensure-fonts.mjs` (the generated font must exist) and `check-brand.mjs` (the
SVGs must parse). Both fail with the one command that fixes them rather than an
error in a file nobody is looking at.

Use `npm run typecheck`, **not** `npx tsc --noEmit`. The root `tsconfig.json` is
solution-style with `files: []`, so `--noEmit` on its own checks nothing and
exits 0. That mistake hid four type errors once already.

## Design system

`src/styles/tokens.css` is the single source of truth. Components name tokens,
never colours, so a palette change touches one file.

### Palette

| Role | Day | Dark |
|---|---|---|
| Background | `#FFFFFF` | `#071426` |
| Surface (cards) | `#FFFFFF` | `#0E2233` |
| Surface elevated (sidebar, dialog, table head) | `#F2F6F8` | `#1F506B` |
| Primary / action | `#4C7C92` | `#B0E1E4` |
| Accent (emphasis) | cream, darkened for text | `#F1E6B6` |
| Text primary | `#16333F` | `#E4F5F6` |

Cream `#F1E6B6`, aqua `#B0E1E4` and blue `#4C7C92` are the given brand values
and appear unmodified. Everything else is a lightness step of the same three
hues, so no new hue was introduced.

### Three decisions worth knowing

**1. The brand blue is not a text colour.** `#4C7C92` on white measures 4.56:1.
That is fine for a button fill and for large text, but it is too light for body
copy. So `--color-primary` is the fill and `--color-text-brand` is a darker step
of the same hue for text. Same reasoning made `--color-text-muted` a darker
slate than it started as: "muted" must mean lower emphasis, not lower contrast.

**2. Dark mode needs two border tokens.** On the card surface `#0E2233` a blue
border is nearly invisible at 2.79:1, so `--color-border-strong` is lighter. On
the elevated surface `#1F506B` the rule is reversed — the border must be *lighter
than the surface*, because a surface that dark leaves no room for a darker
border. Three darker attempts were measured and failed: `#2B6076` 1.26:1,
`#0D2C3D` 1.41:1, `#5D8A9E` 2.31:1. `#7FA8BC` reaches 3.41:1, so the brand
surface stays exactly as specified.

**3. Status colours are derived, and never carry meaning alone.** The palette
has no green or red, so success, warning, error and info are built from the
brand hue by moving lightness. That compresses the distance between states, so
every status also carries a text label and a shape. Colour is reinforcement,
not the signal. The user chose "derive from the palette" over "keep the
existing status colours" and accepted this trade.

### Verification

`tests/tokens.contrast.test.ts` asserts **144 foreground/background pairs** against
WCAG 2.2 AA — text at 4.5:1, large text and meaningful borders at 3:1 — plus a
check that every token declared in `:root` is also overridden in `.dark`. A token
present in one theme only would silently keep its other-theme colour, which is the
failure this catches.

Run it with `npm test`. If you change a colour and a pair fails, the assertion
names both tokens and the measured ratio.

### Readability: the encoding bug that looked like a styling problem

The Reader and the Account panel were reported as "the text is not readable at
all", and the first pass got it wrong. It measured font sizes and contrast,
found a real 11px caption and fixed it, and the complaint did not change — because
the text was not the wrong *size* or the wrong *colour*. It was the wrong
*characters*.

`src/pages/ReaderPage.tsx` and `src/pages/AccountPage.tsx` had every Persian
string double-encoded. The browser was rendering `Ù…Ø¨Ø¯Ø£` where it should
have shown `متن`, `ØªØ±Ø¬Ù…Ù‡` for `ترجمه`, `ÙØµÙ„â€ŒÙ‡Ø§` for `فصل‌ها`.
The product was showing mojibake and calling it a font.

**Nothing in the toolchain can catch this**, which is why it survived:

- a mojibake file is valid UTF-8, so it passes every encoding check
- it is valid TypeScript and valid JSX, so `tsc` and the linter are silent
- `git diff` renders the bytes as the same garbage the user sees, so the damage
  is invisible in review
- the contrast audit reported 622 elements with zero failures, because it
  measures colour and size. The text measured perfectly. The glyphs were simply
  the wrong glyphs.

The only thing that finds it is a check on the *content* of the string, so that
is what `tests/encoding.test.ts` is. It walks `src/`, rejects the Latin-1
signature characters, asserts the bytes are genuinely valid UTF-8, and — in the
other direction — asserts that `src/` still contains real Persian, so the check
cannot pass by the Persian having been deleted. 30 assertions.

`tests/test_encoding.py` does the same for `app/` in the Python repo, where
`app/pipeline/pdf_fixer.py` had 1,317 marker characters across 103 lines of
Persian comments.

**How it happened:** the files passed through more than one codec. The `â€`
sequences prove part of the damage was a UTF-8 read as Windows-1252, while stray
C1 controls (`U+0081`, `U+0090`) prove another part was read as latin-1 — the
only codec that maps those at all. So a plain `cp1252` round trip *fails* on
exactly the files that need it most; the repair falls back to the latin-1 byte
value for whatever cp1252 cannot encode. `docs/fix_mojibake.py` does this and
refuses to write unless the result is unambiguously better.

### Readability: the 12px floor

`--text-caption` was `0.6875rem`, which is **11px**, and it was reported as "the
text is not readable". Latin at 11px is merely small. Persian is different,
because the script joins: the letters need their shapes to be told apart, and at
11px with a 1.6 line height the descenders of one line meet the ascenders of the
next.

So the scale now has a **12px floor**, asserted in the same test file rather than
left to taste, because a scale is exactly the kind of thing that drifts down one
step at a time. The steps were respaced as a consequence:

| step | was | now |
| --- | --- | --- |
| `--text-caption` | 11px | **12px** |
| `--text-label` | 12px | **13px** |
| `--text-button` | 12px | **13px** |
| `--text-small` | 13px | **14px** |

`--text-label` and `--text-button` deliberately share a size, and the test allows
exactly that one repeat: a button label and a field label are the same kind of
thing. Every running-text step also carries a line height of at least 1.6, for
the same reason the floor exists.

### Verification

Tokens alone do not prove a page is readable, because a page composes them
differently from how they are declared. Two things check the composed result:

- **`npm run audit:contrast`** builds the real components, renders every page
  against payloads captured from the running backend, walks the resulting DOM,
  and resolves each text element's colour and the surface behind it by applying
  the cascade to the built stylesheet. Both themes. It reports 622 text elements
  across the five pages: 0 below 3:1, 0 below 4.5:1, 0 below 12px.
- **`node scripts/render-preview.mjs`** writes each page to
  `scripts/preview/*.html` with the stylesheet inlined, so it can be opened in a
  browser. `docs/show_page_text.py` prints the same pages as a text outline with
  the computed size beside each line, which is what settled the 11px question
  without a browser attached.

Both read `scripts/page-data.json`, a snapshot of one real library. It and the
previews are gitignored: they contain book titles and job ids.

The audit found two things the token tests had not, both on the *elevated*
surface, which is a different lightness from the card surface, so a colour that
passes on one can fail on the other: `--color-success` at 4.36:1, `--color-error`
at 4.06:1, `--color-info` at 4.20:1. All three are now lighter steps of the same
hue, and all three pairs are in the token test.

### Also in the system

- **Type scale** — `--text-display` … `--text-button`, in `rem` so browser zoom
  still works
- **Spacing** — a 4px base (`--spacing-1` … `--spacing-12`); every margin and
  padding in the components is one of these
- **Radius** — restrained on purpose: 4/6/8/12/14px, `999px` only for badges
  and progress fills, 16px for modals. Nothing at 20px.
- **Shadow** — day mode uses soft low-opacity shadow; dark mode uses
  `--shadow-card: none` and carries elevation through surface lightness instead,
  because shadow is invisible on a near-black ground.

## Layout

```
docs/inventory/          captured "before" state of the current UI (Phase 0)
src/lib/api.ts           typed bindings, shapes taken from the captured responses
src/lib/format.ts        Persian labels, number/date/byte formatting, badge tones
src/lib/chunks.ts        chunk flag extraction and the three filters
src/lib/virtual.ts       window arithmetic for the virtualised table
src/hooks/               useTheme (shares jbook-study-dark with the Python pages)
src/components/          AppShell (sidebar), ApiStatus
src/components/monitor/  OverviewTab, ChunksTab, QaTab, LogsTab, AssetsTab,
                         VirtualChunkTable
src/pages/               DashboardPage, JobDetailPage, PendingPage
src/styles/tokens.css    the design system: colour, type, spacing, radius, shadow
tests/                   156 tests (33 monitor logic, 123 contrast)
scripts/check-contract.mjs   live contract check against the Python API
```

## Rules that must not drift

1. **Theme key is `jbook-study-dark`.** The Python pages read the same key. Do
   not rename it while both UIs coexist or a user's theme silently resets.
2. **`sanitize_html` stays a Python boundary.** Chapter HTML arrives already
   sanitised from `/api/reader/...`. Render it with `dangerouslySetInnerHTML`
   and never re-implement sanitisation in TypeScript — the security tests in
   `tests/test_reader_images.py` cover the Python side.
3. **`src/styles/tokens.css` is the source of truth for the React UI.** No
   component may name a hex value or a Tailwind colour class. If a new screen
   needs a colour, add a semantic token first and use it.
4. **The Python `design-system/` folder is a separate, older system.** It still
   governs the Python pages. The two are not kept in sync automatically — the
   React palette is its own thing, and a colour decision in one does not
   propagate to the other. If they are meant to converge, that is a deliberate
   task, not a side effect.
5. **API shapes are captured, not guessed.** `docs/inventory/` holds a real
   response for every endpoint, and `npm run check:api` asserts the live backend
   against the types. Re-capture before changing a type.
6. **`ROW_H` lives in `src/lib/virtual.ts` and the `height` in `tokens.css`
   must stay equal.** The virtualiser computes the scroll window arithmetically
   from a fixed row height, so if the CSS and the constant disagree, rows
   overlap and the scrollbar lies. The comment in `.vtable td` points here.

## Migration phases

| Phase | Scope | Status |
|---|---|---|
| 0 | inventory the current UI | done |
| 1 | Vite + strict TS + tokens + API client + shell | done |
| 2 | Job Monitor (`/jobs/:id`) | done |
| 3 | Workspace + Library | done |
| 4 | Reader | done |
| 5 | Account | done |
| 6 | serve `dist/` from Python, delete old templates | **not started** |

### What is still the Python UI

| Route | Owner |
|---|---|
| `/` `/workspace` `/jobs` `/jobs/:id` `/library` `/reader` `/account` | React |
| `/landing` | Python (marketing, not product surface) |
| `/api/*` | Python |

Phase 6 is deliberately not started. It is the only irreversible step, it
requires changing `app/web.py` (which is otherwise frozen), and the bundle audit
in `docs/audit_bundle.py` lists what the backend would need to do first. Run that
script and read its output before deciding.

### Porting notes

Decisions that were not just transliteration:

- **The glossary flow is ported, including the review dialog.** The proposal
  panel and the approve dialog live in `src/components/glossary/`. Only ticked
  terms are promoted, matching `app/glossary/proposal_page.py`.
- **The Reader keeps sanitisation on the Python side.** Chapter HTML is
  sanitised by `sanitize_html` before it reaches this client and is injected
  whole. Do not add client-side sanitisation: it would create a second,
  differently-flawed copy of the one thing that stops a hostile EPUB running
  script in this origin. The tests for that live in the Python project.
- **The form does not hardcode a model.** An empty model field means "the
  configured default", so `config.yaml` decides, as it does everywhere else.
- **`job.reader` is a path, not an id.** Interpolating it as an id produced
  `/api/reader//reader/...` and a 404 that looked like a missing endpoint.
- **The reader's chapter selection is derived, not stored in an effect.** The
  effect version re-fired on refetch and silently pulled the reader back to
  chapter one.

### One bug worth keeping in mind

`docs/check_normalisation.py` feeds the same strings through the Python and
TypeScript term-key functions and diffs them. It exists because a test asserted
that `key()` strips a zero-width non-joiner, and passed — while Python was
keeping it. The JS side had been deleting invisible characters Python kept, so
the two UIs would have disagreed about whether a term was already in the
glossary, and approving a draft would have created a duplicate.

Both keep the ZWNJ, the soft hyphen and the bidi controls. The check runs over 19
awkward inputs and is the reason the two stay in step.

### The chapter title arrives twice

`/api/reader/{id}/chapters/{n}` and every block under it come back shaped like
this, with the chapter title as loose text and then again inside an `<h1>`:

```
\n\n\nمعضل نقشه‌کش\n\n\n<h1>معضل نقشه‌کش</h1><p>…</p>
```

The reader printed the title twice with a blank line between. The loose copy is
not markup, so nothing downstream can remove it.

**This is a Python-side defect** — the chapter builder writes the title and then
the body, which starts with the same title — and it should be fixed in
`app/`, not here. Until it is, `stripDuplicatedHeading` in `src/lib/chunks.ts`
drops both copies, because the reader already shows the title in its own header.

Two functions, not one, because they have different information. `stripLeadingTitle`
is given the title and can remove a lone copy. `stripDuplicatedHeading` has no
title: the bilingual blocks carry the *original* title in `original_html` and the
*translated* one in `translation_html`, so there is no single string to match
both against. It only fires when both copies are present and agree after
normalising whitespace, direction marks and case — guessing which heading is
redundant would risk deleting a chapter's real first section.

## Brand

The mark lives in `public/brand/` as two SVG files, one per theme, and the
favicon is a simplified third.

They are two files rather than one with `currentColor` because they are not
inversions of each other. On the light theme the blue is the ink and the cream
is the paper; on the dark theme the aqua becomes the ink and the document turns
into the pale object. One file cannot express a hue changing roles.

`KalimaMark` in `AppShell.tsx` picks the variant through `useTheme`, so the mark
swaps the instant the toggle is pressed. The Python pages do the same thing with
CSS: both variants are inlined and one is hidden, because
`app/core/brand.py` has no build step to inline with.

`scripts/check-brand.mjs` runs before `dev` and `build`. A `--` inside an XML
comment, or a truncated `<!-` from an over-eager regex, makes the file fail to
parse, so the mark renders as an empty space with nothing in any log. That
happened once during this work; the guard is why it cannot happen twice.

## Fonts

Vazirmatn is served from this origin, not from Google Fonts. `index.html` used to
link `fonts.googleapis.com`, which meant the app needed the internet to render
Persian text and every page view told a third party who was reading.

`../docs/build_fonts.py` copies the woff2 files from the Python project into
`public/fonts/` and writes a small `@font-face` stylesheet. Both outputs are
gitignored: the Python repo is the single source of truth for binary assets, and
duplicating 250 KB of font across two repositories is how they drift.

`npm run dev` and `npm run build` run `scripts/ensure-fonts.mjs` first, which
fails with the one command that fixes it rather than an opaque module-not-found
in `main.tsx`.

The first attempt inlined the font as base64, copying `app/core/fonts.py`. It
worked but pushed the CSS from 29 KB to 370 KB, because base64 in a stylesheet
cannot be cached separately from it.

## Type safety

`tsconfig.app.json` runs `strict`, plus `noUncheckedIndexedAccess`,
`exactOptionalPropertyTypes`, and `erasableSyntaxOnly`. This is deliberate: the
backend is the contract, so `any` leaking into the UI is a bug.

`tsconfig.test.json` is a separate project because the tests run under Node and
must not see `process`, while `src` must not see `node:test`.
