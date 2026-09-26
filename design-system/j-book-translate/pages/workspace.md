# Workspace Page Overrides

> **PROJECT:** J Book Translate
> **Generated:** 2026-09-26
> **Page Type:** Workspace / Translation Studio
> **Source File:** `app/jobs/workspace.py` → `install_workspace()`

> ⚠️ Rules here **override** `MASTER.md`. For all other rules, refer to Master.

---

## Page-Specific Rules

### Theme Sync
- **Source of truth:** `app/jobs/workspace.py` install_workspace()
- **Goal:** Workspace is the primary translation interface.
- **Storage key:** `jbook-study-dark` — same as all other pages

### Layout
- **Three-column layout:** Sidebar | Translation Form | Job Status
- **Sidebar:** Same as dashboard — navigation with active state
- **Main form area:** New translation creation with all options
- **Job status area:** Live progress tracking for active jobs
- **Summary strip** at top of main area

### Translation Form
- **File drop zone:** Accepts `.epub,.pdf` up to 1GB
- **Language selects:** Source (`from_lang`) and Target (`to_lang`)
- **Model select:** Shows available models from `/api/models`
- **Mode select:** Fast / Batch / Batchcheck / Resume
- **Style preset:** Literary / Technical / Conversational / Formal
- **Options:**
  - Auto glossary (checkbox)
  - Preserve author voice (checkbox)
  - Extra outputs: JSON_SEGMENTS, TXT_BILINGUAL, MARKDOWN, DOCX, TRANSLATED_PDF, BILINGUAL_PDF, QUALITY_REPORT
- **Translation prompt:** Textarea with pre-filled default
- **Submit button:** `bg-[var(--ink)] text-white` primary CTA

### Job Status Panel
- Live progress bar per job
- Chunk progress: X / Y chunks complete
- ETA display
- Speed: chunks/minute
- Health indicator: green/yellow/red
- Log streaming
- Actions: Stop, Cancel, Resume per status
- Resume-safe: saves after every chunk

### Sidebar Navigation (Workspace)
- **Sections:** 
  - `⌂ داشبورد` (Dashboard)
  - `＋ ترجمهٔ جدید` (New Translation)
  - `◷ Jobهای فعال` (Active Jobs)
- **Content Management:**
  - `▣ کتابخانه` (Library)
  - `⌘ Glossary` (Glossary)
  - `◒ آمار و هزینه` (Analytics)
- Toast notifications for upcoming features
- Summary card at bottom: Storage, Cost, Provider status

### Anti-patterns
- ❌ Do NOT allow simultaneous translation (RUN_LOCK in web.py)
- ❌ Do NOT use different theme key
- ❌ Do NOT hardcode hex values
- ❌ Do NOT forget RTL adjustments for sidebar
- ❌ Do NOT show job progress without health indicator
- ❌ Do NOT allow form submit without file selected

### Responsive
- Sidebar collapses on mobile with overlay
- Translation form full-width on mobile
- Job status scrolls horizontally if needed
- Drop zone adapts to screen size

---

## Implementation Notes
- File: `app/jobs/workspace.py` → `install_workspace(PAGE)` function
- `PAGE` string in `app/web.py` contains the workspace HTML
- Jobs stored in `JOBS` dict and persisted to `data/jobs/*.json`
- Translation pipeline calls `translate()` from `app/pipeline/pipeline.py`
- Resume supported via `pipeline_job_id` and chunk-level persistence
- Auto glossary syncs via `sync_book()` from `app.glossary.automatic`
- Quality report generated via LLM evaluation (6-dimensional score)
- All API calls use `/api/jobs`, `/api/health`, `/api/dashboard/summary`

### Color Mapping
- Primary CTA: `bg-[var(--ink)]` / `#142033` (light), `bg-white text-[#1E3A5F]` (dark pricing card style)
- Drop zone: `border:1.5px dashed #9...` with `bg-[#F8FAFC]` (light), `linear-gradient(135deg,#252b35,#20252c)` (dark)
- Health indicators: green (#08966c), yellow (#fbbf24), red (#e24a4a)
- Form inputs: `background:var(--surface); color:var(--ink); border-color:var(--line)`
