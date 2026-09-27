# Reader Page Overrides

> **PROJECT:** KALIMA
> **Generated:** 2026-09-26
> **Page Type:** Reader / Study Center
> **Source File:** `app/reader/page.py` → `reader_page()` and `app/reader/service.py`

> ⚠️ Rules here **override** `MASTER.md`. For all other rules, refer to Master.

---

## Page-Specific Rules

### Theme Sync
- **Source of truth:** `app/reader/page.py` reader_page()
- **Goal:** Reader must provide comfortable reading experience in both light and dark modes.
- **Storage key:** `jbook-study-dark` — same as all other pages
- **Reading settings:** Stored in `settings` table with `reading_%` keys

### Reading Settings (Available)
| Setting | Options | Default |
|---------|---------|---------|
| `study_night_mode` | bool | false |
| `reading_theme` | light / dark | light |
| `reading_mode` | translation / original / bilingual | translation |
| `reading_font_size` | 14-28px | 18px |
| `reading_line_height` | 1.5-2.5 | 1.9 |
| `reading_width` | 500-900px | 760px |
| `reading_direction` | auto / ltr / rtl | auto |
| `reading_last_location` | bookmark | null |

### Layout
- **Single-column reading view** — minimal chrome
- **Width:** Configurable via `reading_width` setting (default 760px)
- **Font:** Vazirmatn, size configurable
- **Line height:** 1.9 default, configurable
- **Navigation:** Previous/Next chapter, Table of Contents sidebar
- **Reading mode toggle:** Translation / Original / Bilingual

### Bilingual Mode
- Side-by-side original + translation
- `dir="rtl"` for Persian/Farsi translation
- Column layout: original left, translation right (or vice versa for RTL)
- Highlighted differences and flagged notes visible
- `w:bidi` CSS for proper RTL rendering

### Study Night Mode
- Dark background (`#0e141e`) with warm text (`#d8d2c8`)
- Reduced blue light for evening reading
- Toggle via `study_night_mode` setting
- Persists across sessions

### Navigation
- Chapter list sidebar
- Previous/Next chapter buttons
- Table of Contents
- Last location bookmark
- Progress indicator

### Anti-patterns
- ❌ Do NOT use hardcoded hex values for reader theme
- ❌ Do NOT use different theme key
- ❌ Do NOT break RTL in bilingual mode
- ❌ Do NOT ignore reading settings persistence
- ❌ Do NOT use font sizes below 14px or above 28px
- ❌ Do NOT show page chrome that interferes with reading flow

### Responsive
- Reading width should scale down on smaller screens
- Sidebar should be collapsible/hidable
- Touch-friendly navigation (swipe between chapters if applicable)
- Bilingual view should stack on mobile (original above, translation below)

---

## Implementation Notes
- File: `app/reader/page.py` → `reader_page()` function
- Reading settings from `app/web.py` → `reading_settings()` function
- Chapters from `app/reader.service` → `chapter_blocks()`, `chapters()`, `chapter()`
- Book content loaded from translated EPUB files
- Uses `app.storage.database` for settings persistence
- `app/reader/page.py` includes full HTML page with CSS and JS
- Font: Vazirmatn with `font-size` and `line-height` CSS custom properties

### Reader CSS Variables
```css
.reader-content {
  font-family: Vazirmatn, 'Plus Jakarta Sans', system-ui, sans-serif;
  font-size: var(--reading-font-size, 18px);
  line-height: var(--reading-line-height, 1.9);
  max-width: var(--reading-width, 760px);
  color: var(--ink);
  background: var(--surface);
}
body.app-dark .reader-content {
  color: var(--ink);
  background: var(--surface);
}
body.app-dark [data-study-night] .reader-content {
  background: #0e141e;
  color: #d8d2c8;
}
```
