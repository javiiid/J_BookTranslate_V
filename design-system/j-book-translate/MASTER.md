# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** KALIMA
**Generated:** 2026-09-26
**Category:** Translation Tool / Book Publisher

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary (Ink) | `#142033` | `--ink` |
| Primary Blue | `#356df6` | `--blue` |
| Secondary (Purple) | `#7257e8` | `--purple` |
| Accent/CTA | `#08966c` | `--green` |
| Cyan | `#0ca6a6` | `--cyan` |
| Red | `#e24a4a` | `--red` |
| Amber | `#fbbf24` | `--amber` |
| Background | `#f4f7fb` | `--bg` |
| Surface/Card | `#FFFFFF` | `--surface` |
| Surface-2 | `#f1f3f5` | `--surface-2` |
| Foreground | `#142033` | `--foreground` |
| Muted | `#6d7a90` | `--muted` |
| Muted-2 | `#94a3b8` | `--muted-2` |
| Border | `#e3e9f2` | `--line` |
| Line-Strong | `#2e4056` | `--line-strong` |
| Ring | `#356df6` | `--color-ring` |

**Light → Dark Mapping:**

| Role | Light | Dark | CSS Variable |
|------|-------|------|--------------|
| Background | `#f4f7fb` | `#0e141e` | `--bg` |
| Surface | `#FFFFFF` | `#18202e` | `--surface` |
| Surface-2 | `#f1f3f5` | `#1e293b` | `--surface-2` |
| Ink/Foreground | `#142033` | `#f1f5f9` | `--ink` |
| Ink-Strong | `#142033` | `#ffffff` | `--ink-strong` |
| Muted | `#6d7a90` | `#b8c6d6` | `--muted` |
| Muted-2 | `#94a3b8` | `#94a3b8` | `--muted-2` |
| Border | `#e3e9f2` | `#243142` | `--line` |
| Blue | `#356df6` | `#60a5fa` | `--blue` |
| Purple | `#7257e8` | `#a78bfa` | `--purple` |
| Green | `#08966c` | `#34d399` | `--green` |
| Shadow | `0 18px 55px rgba(38,57,93,.08)` | `0 18px 55px rgba(0,0,0,.45)` | `--shadow` |

**Color Notes:** Navy/blue professional + paid green for CTA + Persian-first with OLED-friendly dark mode.

### Typography

- **Heading Font:** Vazirmatn (Persian), Plus Jakarta Sans (Latin fallback)
- **Body Font:** Vazirmatn, 'Plus Jakarta Sans', system-ui, sans-serif
- **Mood:** professional, clean, approachable, functional, high contrast
- **Google Fonts:** [Vazirmatn + Plus Jakarta Sans](https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap)
- **RTL Support:** Native RTL with `dir="rtl"` and `lang="fa"`

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
```

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |
| `--shadow-soft` | `0 18px 55px rgba(38,57,93,.08)` | Landing soft shadow |
| `--shadow-card` | `0 12px 32px rgba(38,57,93,.07)` | Card elevation |

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | `8px` | Buttons, inputs, badges |
| `--radius-md` | `12px` | Cards, dropdowns |
| `--radius-lg` | `20px` | Modal, form cards |
| `--radius-xl` | `24px` | Landing sections |
| `--radius-2xl` | `28px` | Hero cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: var(--ink); /* #142033 */
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
  border: none;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: var(--ink);
  border: 2px solid var(--line);
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

/* Blue CTA */
.btn-blue {
  background: var(--blue); /* #356df6 */
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
  border: none;
}

.btn-blue:hover {
  background: #254eda;
  box-shadow: 0 4px 14px rgba(53,109,246,.25);
}

/* Green Accent */
.btn-accent {
  background: var(--green); /* #08966c */
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
  border: none;
}
```

### Cards

```css
.card {
  background: rgba(255,255,255,.92);
  border: 1px solid rgba(224,230,240,.9);
  border-radius: 20px;
  padding: 24px;
  box-shadow: var(--shadow);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-card);
  transform: translateY(-2px);
}

body.app-dark .card {
  background: rgba(34,37,43,.96);
  border-color: #343941;
  box-shadow: var(--shadow);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 16px;
  font-family: inherit;
  transition: border-color 200ms ease;
  background: var(--surface);
  color: var(--ink);
}

.input:focus {
  border-color: var(--blue);
  outline: none;
  box-shadow: 0 0 0 3px rgba(53,109,246,.2);
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: var(--surface);
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

### Sidebar (Dashboard)

```css
.app-sidebar {
  position: fixed;
  z-index: 10;
  right: 18px; /* RTL */
  top: 18px;
  bottom: 18px;
  width: 250px;
  padding: 18px 14px;
  background: rgba(255,255,255,.94);
  border: 1px solid #e2e8f2;
  border-radius: 20px;
  box-shadow: 0 18px 55px rgba(38,57,93,.1);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

body.app-dark .app-sidebar {
  background: rgba(34,37,43,.96);
  border-color: #343941;
}

.shell {
  margin-right: 292px; /* RTL sidebar offset */
  max-width: calc(1180px - 292px);
}
```

### Dashboard Cards

```css
.dashboard-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 11px;
  margin-bottom: 18px;
}

.dashboard-card {
  padding: 14px;
  background: var(--surface);
  border: 1px solid #e5ebf4;
  border-radius: 14px;
  box-shadow: 0 8px 20px rgba(38,57,93,.06);
}
```

---

## Style Guidelines

**Style:** Minimalism & Swiss Style + Persian RTL-first

**Keywords:** Clean, simple, spacious, functional, white space, high contrast, geometric, sans-serif, grid-based, essential, RTL-native

**Best For:** Professional tools, dashboards, word by word, book by books, documentation sites, publisher platforms

**Key Effects:** Subtle hover (200-250ms), smooth transitions, sharp shadows, clear type hierarchy, fast loading, RTL-aware animations

### Page Pattern

**Pattern Name:** Trust & Authority + Conversion + RTL-First

- **Conversion Strategy:** Security badges, case studies, transparent pricing, low-friction form, RTL-native flow
- **CTA Placement:** Start translating (primary) + Nav
- **Section Order:** Hero (mission/credibility) > Proof (logos, certs, stats) > Solution overview > How it works > Formats > Security > Pricing > Testimonials > FAQ > CTA
- **RTL Consideration:** All layouts mirror for RTL; flex-direction: row-reverse where needed; text-align: right

---

## Theme System (Dark Mode)

### Light Mode (Default)
```css
:root {
  --bg: #f4f7fb;
  --surface: #fff;
  --ink: #142033;
  --muted: #6d7a90;
  --line: #e3e9f2;
  --blue: #356df6;
  --purple: #7257e8;
  --green: #08966c;
  --shadow: 0 18px 55px rgba(38,57,93,.08);
}
```

### Dark Mode (OLED-friendly)
```css
body.app-dark {
  --bg: #0e141e;
  --surface: #18202e;
  --surface-2: #1e293b;
  --ink: #f1f5f9;
  --ink-strong: #ffffff;
  --muted: #b8c6d6;
  --muted-2: #94a3b8;
  --line: #243142;
  --line-strong: #2e4056;
  --blue: #60a5fa;
  --blue-soft: #1e3a5a;
  --purple: #a78bfa;
  --green: #34d399;
  --amber: #fbbf24;
  --shadow: 0 18px 55px rgba(0,0,0,.45);
}
```

**Theme Toggle:**
- Storage key: `jbook-study-dark` (`'1'` = dark)
- Same key used across landing, dashboard, library, workspace
- Toggle button: `#theme-toggle` with sun/moon SVGs
- **Do NOT use** `kalima-theme` or `html.dark`

### Dark Mode Anti-patterns (Do NOT Use)
- ❌ Pure black (#000000) backgrounds — use deep navy (#0e141e) for OLED comfort
- ❌ White (#FFFFFF) surfaces — use #18202e for reduced glare
- ❌ No text-shadow glow effects — keep text crisp
- ❌ No neon color spill — limit vibrant accents to small UI elements only

---

## RTL / Persian-Specific Rules

- `dir="rtl"` on `<html>` when language is Persian
- `lang="fa"` on `<html>` for Persian content
- All flex containers should support `flex-direction: row-reverse` for RTL
- Padding/margin-right becomes padding/margin-left in RTL context
- Use CSS logical properties (`margin-inline-start`, `padding-inline-end`) where possible
- Icon SVGs should be flipped for RTL where directional (arrow, chevron)
- `text-align: right` for Persian text
- Focus states should be visible on both LTR and RTL layouts
- Vazirmatn font must load first; Plus Jakarta Sans as Latin fallback

---

## Viewport Units & Mobile
- Use `min-h-dvh` instead of `min-h-screen` for full-screen mobile layouts
- `100vh` is problematic on mobile browsers with address bars
- **Code:** `min-height: 100dvh;` or Tailwind `min-h-dvh`
- **Don't:** Use `h-screen` for full-screen mobile layouts

---

## Z-Index Scale
- Use Tailwind `z-*` scale consistently: `z-0 z-10 z-20 z-30 z-40 z-50`
- **Don't:** Arbitrary z-index values like `z-[9999]`
- **Stack for KALIMA:**
  - `z-10` — Sidebar (`app-sidebar`)
  - `z-20` — Global language switcher (`#global-language`)
  - `z-30` — Modal overlay
  - `z-40` — Toast notifications
  - `z-50` — Modal content (above overlay)
- **Code:** `z-50 for modals`, `z-10 for sidebar`

---

## GSAP Animations

### Scroll Reveal (Subtle)
- **Trigger:** scroll (viewport enter)
- **Duration:** 300-400ms
- **Easing:** `power1.out`
- **Code:**
```js
gsap.from(el, { opacity: 0, y: 12, duration: 0.35, ease: 'power1.out',
  scrollTrigger: { trigger: el, start: 'top 90%', toggleActions: 'play none none reverse' } });
```
- **Use for:** Feature cards, section entries, testimonial cards

### Stagger List (Subtle)
- **Trigger:** load or scroll
- **Duration:** 250-350ms, stagger 0.03s
- **Easing:** `power1.out`
- **Code:**
```js
gsap.from('.list-item', { opacity: 0, y: 8, duration: 0.3, stagger: 0.03 });
```
- **Use for:** Feature grid, dashboard cards, book list items

### SplitText Headline (Complex)
- **Trigger:** load
- **Duration:** 400-700ms, `expo.out`
- **Code:**
```js
const split = new SplitText(headline, { type: 'chars' });
gsap.from(split.chars, { opacity: 0, y: 20, rotateX: -40, duration: 0.6, stagger: 0.015, ease: 'expo.out' });
```
- **Use for:** Hero headline only (under ~8 words)
- **Don't:** Split-animate long paragraphs

### Reduced Motion
- Always use `matchMedia('(prefers-reduced-motion: reduce)')` to skip motion
- **Code:**
```js
if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  gsap.set('.feature-card', { opacity: 1, y: 0 });
}
```
- **Cleanup:** Call `split.revert()` on unmount

### ScrollPadding for Sticky Headers
- **Do:** `scroll-padding-top: var(--header-height)` on `html` or `body`
- **Don't:** Let sticky headers cover focused elements
- **Code:** `html { scroll-padding-top: 64px; }` (header height)
- **Sidebar:** `scroll-margin-right: 292px` to account for sidebar

---

## Anti-Patterns (Do NOT Use)

- ❌ Excessive decoration
- ❌ Complex shadows
- ❌ 3D effects
- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Phosphor)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y
- ❌ **Pure black dark backgrounds** — Use deep navy (#0e141e) for OLED eye comfort
- ❌ **Different theme keys** — Only `jbook-study-dark` is valid
- ❌ **Hardcoded hex in HTML classes** — Use CSS variables via stylesheet overrides
- ❌ **English-only content** — All UI must support Farsi/English via i18n system

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG)
- [ ] All icons from consistent icon set (Heroicons/Lucide/Phosphor)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Dark mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
- [ ] RTL support verified (`dir="rtl"`, `lang="fa"`)
- [ ] Theme toggle works and persists via `jbook-study-dark`
- [ ] Vazirmatn font loads before Plus Jakarta Sans
- [ ] All CSS uses semantic variables, not hardcoded hex
- [ ] i18n language switcher functional (`jbook-language`)
- [ ] Dark mode background uses #0e141e not #000000
