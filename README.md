# J Translate UI

The new React front end for J Book Translate.

## Why this is a separate repository

The Python project at `D:\J_BookTranslate_V` is **frozen and untouched**. It already
exposes everything as a plain HTTP API under `/api/*`, so the UI needs no shared
code, only a network call. That gives:

- zero regression risk to the 214 Python tests
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
| `npm run build` | type-check (`tsc -b`) then production build to `dist/` |
| `npm run preview` | serve the built bundle |
| `npx tsc --noEmit` | types only |

## Layout

```
docs/inventory/     captured "before" state of the current UI (Phase 0)
src/lib/api.ts      typed bindings, shapes taken from the captured responses
src/lib/format.ts   Persian labels + number/date/byte formatting
src/hooks/          useTheme (shares jbook-study-dark with the Python pages)
src/components/     AppShell, Sidebar, ApiStatus
src/pages/          DashboardPage, PendingPage
src/styles/         tokens.css ported from design-system/MASTER.md
```

## Rules that must not drift

1. **Theme key is `jbook-study-dark`.** The Python pages read the same key. Do
   not rename it while both UIs coexist or a user's theme silently resets.
2. **`sanitize_html` stays a Python boundary.** Chapter HTML arrives already
   sanitised from `/api/reader/...`. Render it with `dangerouslySetInnerHTML`
   and never re-implement sanitisation in TypeScript — the security tests in
   `tests/test_reader_images.py` cover the Python side.
3. **Tokens come from `design-system/`.** When a colour or spacing value
   changes, change it in the Python `design-system/` folder first, then mirror
   it into `src/styles/tokens.css`.
4. **API shapes are captured, not guessed.** `docs/inventory/` holds a real
   response for every endpoint. Re-capture it before changing a type.

## Migration phases

| Phase | Scope | Status |
|---|---|---|
| 0 | inventory the current UI | done |
| 1 | Vite + strict TS + tokens + API client + shell | done |
| 2 | Job Monitor (`/jobs/:id`) | next |
| 3 | Workspace + Library | |
| 4 | Reader | |
| 5 | Account + Welcome + Landing | |
| 6 | serve `dist/` from Python, delete old templates | |

## Type safety

`tsconfig.app.json` runs `strict`, plus `noUncheckedIndexedAccess`,
`exactOptionalPropertyTypes`, and `erasableSyntaxOnly`. This is deliberate: the
backend is the contract, so `any` leaking into the UI is a bug.
