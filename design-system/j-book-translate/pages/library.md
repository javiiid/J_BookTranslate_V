# Library Page Overrides

> **PROJECT:** J Book Translate
> **Generated:** 2026-09-26
> **Page Type:** Library / Content Management
> **Source File:** `app/library/view.py` → `library_page()`

> ⚠️ Rules here **override** `MASTER.md`. For all other rules, refer to Master.

---

## Page-Specific Rules

### Theme Sync
- **Source of truth:** `app/library/view.py` library_page()
- **Goal:** Library must feel like the same product as landing and dashboard.
- **Storage key:** `jbook-study-dark` — same as all other pages

### Layout
- **Grid view:** `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))` for book cards
- **List view:** Single column with file details
- **Search bar:** Prominent at top with debounced input
- **Filter chips:** Status (All, Completed, Running, Failed) + Format (All, EPUB, PDF)
- **Book card:** Cover image area, title, author, status badge, actions (Read, Download, Delete, Archive)

### Book Card
- `background:var(--surface); border:1px solid var(--line); border-radius:20px`
- Hover: `box-shadow:var(--shadow-card); transform:translateY(-2px)`
- Status indicator dot: green (completed), yellow (running), red (failed)
- Actions menu: Read, Download, Delete, Archive
- Grid view shows cover/preview area
- List view shows full metadata

### Library Summary
- Total books count
- Total size used
- Free space remaining
- Storage visualization
- `side-summary` class for sidebar storage card

### Search & Filter
- Search input with placeholder "جست‌وجوی نام کتاب…" (Persian)
- Filter buttons: All statuses, All formats
- Grid/List view toggle
- Pagination if books exceed limit

### Anti-patterns
- ❌ Do NOT use different theme key
- ❌ Do NOT hardcode hex values in book card CSS
- ❌ Do NOT forget RTL for Persian search/UI
- ❌ Do NOT show book content directly in library — only metadata and actions
- ❌ Do NOT allow deleting without confirmation

### Responsive
- Grid cards: 3 columns on desktop, 2 on tablet, 1 on mobile
- Filter bar wraps on small screens
- Search input full-width on mobile

---

## Implementation Notes
- File: `app/library/view.py` → `library_page()` function
- Uses database: `db.fetch_all("SELECT * FROM library_books...")`
- Search and filter done server-side
- Books connected to jobs via `job_id` in `files` table
- Status derived from job status or file kind (original/translated)
- Reading settings stored in `settings` table with `reading_%` keys
- Cover images stored in `data/` directory

### Color Mapping for Library
- Card background: `var(--surface)` / `#fff` (light), `rgba(34,37,43,.96)` / `#1d2025` (dark)
- Borders: `var(--line)` / `#e3e9f2` (light), `#343941` (dark)
- Status badges follow the same badge system as dashboard
- Search input: `background:var(--surface); color:var(--ink); border-color:var(--line)`
