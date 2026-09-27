# Glossary Page Overrides

> **PROJECT:** KALIMA
> **Generated:** 2026-09-26
> **Page Type:** Glossary / Term Management
> **Source File:** `app/glossary/service.py` → `get_glossary()`, `save_glossary()` and `app/glossary/automatic.py` → `sync_book()`

> ⚠️ Rules here **override** `MASTER.md`. For all other rules, refer to Master.

---

## Page-Specific Rules

### Theme Sync
- **Source of truth:** `app/glossary/service.py` and `app/glossary/automatic.py`
- **Goal:** Glossary must integrate seamlessly with translation workflow.
- **Storage key:** `jbook-study-dark` — same as all other pages

### Layout
- **Two-panel layout:** Glossary list (left/top) + Editor (right/bottom)
- **Search bar** at top for filtering terms
- **Term list:** Each entry shows Persian term, English translation, type, notes
- **Editor panel:** Form for adding/editing terms
- **Auto-generate section:** Toggle for automatic glossary generation during translation

### Glossary Entry
- **Fields:**
  - Source term (Persian/English)
  - Target translation
  - Term type (proper noun, technical, common, abbreviation)
  - Notes/context
  - Book association
- **Status indicators:** Manual (user-created) vs. Auto-generated (LLM)
- **Snapshot:** Glossary snapshot saved per job in `data/jobs/{job_id}/glossary.json`
- **Sync:** `sync_book()` maintains glossary consistency across job runs

### Manual vs Automatic
- **Manual glossary:** User creates and edits terms directly
- **Auto glossary:** Generated during translation, can be toggled on/off
- **Warning:** Auto-generation may increase API calls and costs
- **Toggle in translation form:** `auto_glossary` checkbox

### Glossary in Translation
- Glossary terms injected into translation prompts
- Consistent terminology across all chunks
- Snapshot preserved per job for reproducibility
- `{NOTE:}` and `{BOUNDARY_WARNING}` highlighted in QA

### Anti-patterns
- ❌ Do NOT use different theme key
- ❌ Do NOT hardcode hex values in glossary UI
- ❌ Do NOT allow glossary terms to be lost on job restart
- ❌ Do NOT auto-generate glossary without user consent (cost warning)
- ❌ Do NOT show glossary terms without book association
- ❌ Do NOT use emoji icons in glossary entries

### Responsive
- Glossary list: scrollable sidebar on desktop, collapsible on mobile
- Editor: full-width on mobile
- Search: prominent on all sizes
- Term entries should wrap properly in RTL

---

## Implementation Notes
- File: `app/glossary/service.py` → `get_glossary()`, `save_glossary()`
- Auto: `app/glossary/automatic.py` → `sync_book(db, paths)`
- Glossary data stored in SQLite database via `db` object
- Job-specific snapshots in `data/jobs/{job_id}/glossary.json`
- `app/web.py` injects glossary controls into translation form
- Auto glossary note: "برای ثبات اصطلاحات، واژه‌نامهٔ خودکار ترجمه را ترتیبی می‌کند"
- Glossary is per-book, not global — each book has its own glossary

### Glossary UI Colors
- Manual terms: `bg-emerald-50 text-emerald-700` (light), `bg-[#0f2e22] text-[#6ee7b7]` (dark)
- Auto terms: `bg-blue-50 text-blue-700` (light), `bg-[#172a4a] text-[#93c5fd]` (dark)
- Flagged terms: `bg-amber-50 text-amber-700` (light), `bg-[#2e2400] text-[#fde68a]` (dark)
- Borders: `var(--line)` / `#e3e9f2` (light), `#343941` (dark)
