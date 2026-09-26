# Landing Page Overrides

> **PROJECT:** J Book Translate
> **Generated:** 2026-09-26
> **Page Type:** Landing / Marketing — synced to Library/Workspace theme
> **Source File:** `landing.html` (served at `GET /landing`)

> ⚠️ Rules here **override** `MASTER.md`. For all other rules, refer to Master.

---

## Page-Specific Rules

### Theme Sync
- **Source of truth:** `landing.html` → `app/web.py` PAGE → `app/library/page.py`
- **Goal:** Landing feels like the same product as `/library` and `/workspace`, not a separate marketing skin.
- **Background:** `radial-gradient(circle at 8% 0,#e6efff 0,transparent 32%),radial-gradient(circle at 96% 11%,#eee9ff 0,transparent 27%),var(--bg)` with `--bg:#f4f7fb`
- **Dark:** `body.app-dark` with `--bg:#0e141e;--surface:#18202e;--ink:#f1f5f9;--muted:#b8c6d6;--line:#243142;--shadow:0 18px 55px rgba(0,0,0,.45)` + same gradients `#1e293b`/`#1e1b4b`
- **Storage key:** `jbook-study-dark` (`'1'` = dark) — **same as library/workspace**, so theme persists across `/`, `/landing`, `/library`, `/workspace`. Do NOT use `jbt-theme` or `html.dark`.

### Color Overrides

| Role | MASTER | Landing (synced) | CSS Variable |
|------|--------|------------------|--------------|
| Primary (CTA, nav) | `#142033` | `#142033` (ink) / `#356df6` (blue) | `--ink` / `--blue` |
| Secondary | `#2563EB` | `#7257e8` (purple) | `--purple` |
| Accent | `#08966c` | `#08966c` | `--green` |
| Background | `#f4f7fb` | `#f4f7fb` | `--bg` |
| Surface/Card | `#FFFFFF` | `#fff` / `rgba(255,255,255,.92)` | `--surface` |
| Muted | `#6d7a90` | `#6d7a90` | `--muted` |
| Border | `#e3e9f2` | `#e3e9f2` / `rgba(224,230,240,.9)` | `--line` |
| Shadow | soft | `0 18px 55px rgba(38,57,93,.08)` | `--shadow` |

Mapping is done via CSS overrides: `.bg-[#F8FAFC]{background:var(--bg)!important}` etc., and `body.app-dark` overrides. Do not hardcode new hex in HTML classes; keep Tailwind arbitrary values but override via stylesheet.

### Typography Overrides
- **MASTER:** Vazirmatn + Plus Jakarta Sans
- **Landing:** `font-family: Vazirmatn, 'Plus Jakarta Sans', system-ui, sans-serif` — Vazirmatn first to match library (Persian-first), Plus Jakarta as Latin fallback.
- Import: `https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap`
- Headings: `font-extrabold tracking-tight`, body `15px` like workspace.

### Component Overrides
- **Cards:** `background:rgba(255,255,255,.92);border:1px solid rgba(224,230,240,.9);border-radius:20px;box-shadow:var(--shadow)` (library card)
- **Header:** `sticky backdrop-blur bg-[var(--surface)]/80 border-b border-[var(--line)]` with logo gradient `linear-gradient(140deg,var(--blue),var(--purple))`
- **Buttons:** primary `bg-[var(--ink)] text-white` (or `var(--blue)`), secondary `border-[var(--line)] bg-[var(--surface)]`
- **Toggle:** `#theme-toggle` same as workspace/library — sun/moon SVGs, JS toggles `body.app-dark` and `localStorage jbook-study-dark`, syncs icon display.
- **Language toggle:** `#lang-toggle` with فا/EN text, switches `jbook-language` locale

### Layout
- Max width `1280px`, `grid lg:grid-cols-[1.05fr_.95fr]` hero, `8dk` rhythm
- No sidebar on landing (unlike workspace)
- Sections: Hero → Proof → Features → How it works → Formats → Security → Pricing → Testimonials → FAQ → CTA
- Dark section `#how` uses `#0F172A` background with white text
- Pricing popular card uses `#1E3A5F` gradient

### Anti-patterns Specific to Landing
- ❌ Do NOT add `app-sidebar` — landing is standalone marketing
- ❌ Do NOT use different theme key than `jbook-study-dark`
- ❌ Do NOT use emoji as icons (already replaced with SVG in current code)
- ❌ Do NOT hardcode hex values in HTML classes — use CSS variable overrides
- ❌ Do NOT use `html.dark` or `jbt-theme` for dark mode
- ❌ Do NOT break RTL — `dir="ltr"` is correct for landing (English-first marketing)
- ❌ Do NOT use `z-[9999]` — use Tailwind `z-*` scale
- ❌ Do NOT use `100vh` for full-height — use `min-h-dvh`
- ❌ Do NOT stack fixed elements without scroll-padding
- ❌ Do NOT animate long paragraphs with SplitText — reserve for headlines only

### GSAP Animation Requirements
- **Scroll reveal** for feature cards and section entries (300-400ms, power1.out)
- **Stagger list** for feature grid and dashboard cards (0.03s stagger)
- **SplitText** for hero headline only (under 8 words, 400-700ms, expo.out)
- **Always** respect `prefers-reduced-motion` — skip all GSAP animations
- **Always** call `split.revert()` on cleanup for accessibility
- **Scroll padding** must account for sticky header (`scroll-padding-top: 64px`)

### Accessibility for SVG Icons
- **Decorative SVGs** beside visible text: `aria-hidden="true"`
- **Meaningful SVGs** without equivalent text: provide `aria-label` or `<title>`
- **Interactive SVGs** (theme toggle): already have `aria-label` on the button — ✅
- **Icon sizing:** Consistent 16-18px for UI icons, 18px for feature card icons
- **Stroke consistency:** All SVGs use `stroke-width="2"` for uniform appearance

### i18n Requirements
- `#global-language` button toggles between English and فارسی
- `#global-language` button toggles between English and فارسی
- Translation data in `app/core/web_i18n.py` TRANSLATIONS dict
- MutationObserver watches for dynamically added text nodes
- Language persisted in `localStorage.getItem('jbook-language')`

---

## Implementation Notes
- File: `landing.html` (40–45KB) served at `GET /landing` via `app/web.py`
- Tailwind CDN `darkMode:'class'` is set but dark is driven by `body.app-dark` manual overrides, not `html.dark`, to stay synced with library.
- Init script runs before paint, checks `localStorage.getItem('jbook-study-dark')==='1'` → `document.body.classList.add('app-dark')`
- Toggle script updates same key and syncs sun/moon `display` styles.
- Testimonial carousel with keyboard navigation, pause on hover/focus, reduced-motion support
- No `jbt-theme` key — removed.
- All SVG icons must use Lucide/Phosphor, not emoji characters

---

## Recommendations
- When changing library/workspace palette, update landing's `:root` and `body.app-dark` blocks to match.
- Keep Vazirmatn import; do not revert to Plus Jakarta only.
- If adding new sections to landing.html, update this page file accordingly.
- RTL considerations: landing uses `dir="ltr"` for English marketing; all RTL changes are in dashboard/library/workspace pages.
- Focus states must be visible (`outline:2px solid var(--color-ring);outline-offset:2px`).
- All clickable elements must have `cursor:pointer`.
- **GSAP animations:** Scroll reveal for feature cards, stagger for grids, SplitText for hero headline — all respect `prefers-reduced-motion`.
- **SVG icons:** All decorative SVGs must have `aria-hidden="true"`. Interactive SVGs need `aria-label` on their parent button.
- **Viewport units:** Use `min-h-dvh` instead of `100vh` for full-height layouts.
- **Z-index:** Use Tailwind `z-*` scale only (`z-10` sidebar, `z-50` modals). Never `z-[9999]`.
- **Scroll padding:** `html { scroll-padding-top: 64px; }` to prevent sticky header from obscuring focus.
