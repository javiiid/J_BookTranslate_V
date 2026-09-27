# Dashboard Page Overrides

> **PROJECT:** KALIMA
> **Generated:** 2026-09-26
> **Page Type:** Dashboard / Workspace
> **Source File:** `app/web.py` → `PAGE` and `SIDEBAR_HTML`

> ⚠️ Rules here **override** `MASTER.md`. For all other rules, refer to Master.

---

## Page-Specific Rules

### Theme Sync
- **Source of truth:** `app/web.py` PAGE constant + `SIDEBAR_HTML`
- **Goal:** Dashboard must feel like the same product as landing and library.
- **Background:** Same `body.app-dark` / light mode variables from MASTER
- **Storage key:** `jbook-study-dark` — same as all other pages

### Layout
- **Shell layout:** Dashboard grid with sidebar + main content area
- **Sidebar:** `position:fixed;right:18px;top:18px;bottom:18px;width:250px` (RTL)
- **Main content margin:** `margin-right: 292px` to account for sidebar
- **Shell max-width:** `calc(1180px - 292px)`
- **Sidebar sections:** Navigation (Dashboard, New Translation, Jobs) → Content Management (Library, Glossary, Analytics) → Summary card

### Dashboard Cards
- 4-card grid: Active Jobs, Paused, Completed, Failed
- Grid: `grid-template-columns: repeat(4, 1fr); gap: 11px`
- Card styling: `padding:14px; background:#fff; border:1px solid #e5ebf4; border-radius:14px`
- Dark mode: `background:#1d2025; border-color:#343941`

### Summary Strip
- Shows: Books count, Free space, Provider status, Cost
- Displayed between sidebar and content area
- Uses `summary-strip` class

### Form Card (New Translation)
- `class="card form-card"` with `padding:27px`
- Drop zone: dashed border, accepts `.epub,.pdf`
- Grid 2-column for language/model selects
- Style preset select: literary/technical/conversational/formal
- Checkboxes: auto_glossary, preserve_voice
- Output format checkboxes: json_segments, txt_bilingual, markdown, docx, translated_pdf, bilingual_pdf, quality_report

### Job List
- Job cards with status indicators (green/yellow/red health dots)
- Progress bar per job with chunk count and ETA
- Actions: Start, Stop, Cancel, Resume per job status
- Log viewer panel
- Rescue download available

### Convert Card
- Separate card for format conversion without AI
- Drop zone for `.epub,.pdf,.srt,.txt,.md`
- Output format checkboxes
- Result display with download links

### Sidebar Navigation
- Icons use Unicode symbols: ⌂ (Dashboard), ＋ (New), ◷ (Jobs), ▣ (Library), ⌘ (Glossary), ◒ (Analytics)
- Active state: `background:#edf3ff; color:#2e62dc`
- Dark active state: `background:#29344b; color:#b8caff`
- Toast notifications for not-yet-implemented features

### Sidebar Toast
- `#sidebar-toast` element for brief notifications
- Auto-dismiss after 3 seconds
- Shows data retrieval status

### Error Summary & Validation
- **Error summary** must be focusable and placed at top of translation form
- Use `role="alert"` on error containers for screen reader announcement
- Use `aria-describedby` linking each input to its inline error message
- After failed submit, move focus to error summary heading (`tabindex="-1"`)
- **Code pattern:**
```html
<div role="alert" tabindex="-1" aria-labelledby="error-title">
  <h2 id="error-title">There is a problem</h2>
  <a href="#job">View job status</a>
</div>
```
- **Inline errors:** Each invalid field gets `<p id="field-error">` with `aria-describedby="field-error"` on the input
- **Job errors:** `_friendly_error()` returns localized error strings — must be wrapped in `role="alert"` container

### Z-Index Scale (Dashboard)
- `z-40` — Sidebar (`app-sidebar`) — above all content
- `z-50` — Modal overlays and toast notifications
- `z-10` — Global language switcher (`#global-language`)
- `z-30` — Job card dropdown menus
- **Don't use** `z-[9999]` — use Tailwind scale only

### Scroll-Padding
- `html { scroll-padding-top: 64px; }` — prevents sticky header from covering focused elements
- Sidebar at `position:fixed;right:18px` must not obscure focused inputs
- `scroll-margin-right: 292px` on main content to account for sidebar width

### Anti-patterns
- ❌ Do NOT change sidebar width without updating shell margin
- ❌ Do NOT use different storage key than `jbook-study-dark`
- ❌ Do NOT add `app-sidebar` to landing page — it's dashboard-only
- ❌ Do NOT hardcode hex in sidebar CSS — use CSS variables
- ❌ Do NOT forget RTL adjustments for sidebar (right:18px, margin-right:292px)
- ❌ Do NOT use `z-[9999]` — use Tailwind z-* scale
- ❌ Do NOT omit `role="alert"` on error containers
- ❌ Do NOT let sticky header obscure focused form elements

### Responsive
- On small screens, sidebar should overlay or collapse
- Shell margin should adjust when sidebar is hidden
- Dashboard cards should reflow: `repeat(2, 1fr)` on tablet, `1fr` on mobile

---

## Implementation Notes
- File: `app/web.py` — `PAGE` and `SIDEBAR_HTML` constants
- Sidebar installed via `install_jobs_dashboard(PAGE)` and `install_workspace(PAGE)`
- Theme toggle injected via script tag before `</body>`
- `app-intro` class adds animation on first load, removed after 1400ms
- All fetch calls use `/api/` endpoints
- Dark mode overrides are inline in PAGE string via `body.app-dark` CSS
- Convert card injected via `PAGE.replace('</section><aside class="side">', CONVERT_CARD_HTML + ...)`

### Color Mapping for Dashboard (Dark Mode)
```css
body.app-dark .card, body.app-dark .app-sidebar {
  background: rgba(34,37,43,.96);
  border-color: #343941;
}
body.app-dark input, body.app-dark select, body.app-dark textarea {
  background: #1d2025;
  color: var(--ink);
  border-color: #3b424d;
}
body.app-dark .drop {
  background: linear-gradient(135deg,#252b35,#20252c);
  border-color: #546b92;
}
body.app-dark .side-nav button {
  color: #aaaeb8;
}
```
