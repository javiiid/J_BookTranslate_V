/**
 * Render the mobile bottom bar, in both themes and in every selection state, so
 * it can be looked at.
 *
 * The same approach as `render-preview.mjs`, for the same reason: there is no
 * browser in this session, so the markup is rendered to a self-contained HTML
 * file with the real stylesheet inlined. Opening it shows the real design system
 * rather than unstyled markup, and the file is written at a 393px viewport so the
 * bar is laid out at the width it was designed for.
 *
 * Every selection state is rendered, not just one. A bar can be correct when the
 * first item is selected and wrong when the third is -- the indicator fill
 * differs per theme, and the resting primary wash only shows when the primary
 * item is *not* the selected one. Rendering one state would hide exactly the
 * cases that break.
 */
import { build } from 'vite'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync, readdirSync, rmSync, writeFileSync, mkdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'

const here = dirname(fileURLToPath(import.meta.url))
const ui = join(here, '..')
const outDir = join(ui, 'node_modules', '.tmp', 'mobilenav')

rmSync(outDir, { recursive: true, force: true })
await build({
  root: ui,
  logLevel: 'error',
  build: {
    outDir,
    emptyOutDir: true,
    lib: { entry: join(here, 'nav-entry.ts'), formats: ['es'], fileName: () => 'nav.js' },
    rollupOptions: {
      external: [
        'react',
        'react/jsx-runtime',
        'react-dom',
        'react-dom/server',
        'react-router-dom',
        'react-router',
        '@tanstack/react-query',
      ],
    },
    minify: false,
  },
})

const { MobileNav } = await import(
  new URL(`file://${join(outDir, 'nav.js').replace(/\\/g, '/')}`).href
)

const { MOBILE_NAV } = await import(new URL('../src/components/nav.ts', import.meta.url).href)

const assetsDir = join(ui, 'dist', 'assets')
const cssFile = readdirSync(assetsDir).find((n) => n.endsWith('.css'))
const css = readFileSync(join(assetsDir, cssFile), 'utf8')

/** One bar per possible selection, in a labelled strip. */
function render() {
  const rows = MOBILE_NAV.map((item) =>
    renderToStaticMarkup(
      createElement(MemoryRouter, { initialEntries: [item.to] }, createElement(MobileNav)),
    ),
  )
  return rows
    .map(
      (bar) => `<figure class="frame">
  <figcaption>${MOBILE_NAV.find((i) => bar.includes(`href="${i.to}" aria-current="page"`))?.label ?? '?'}</figcaption>
  ${bar}
</figure>`,
    )
    .join('\n')
}

const light = `<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KALIMA - bottom bar (light)</title>
<style>${css}
  body { background: var(--color-background); }
  .strip { display: flex; flex-direction: column; gap: 2.5rem; padding: 1.5rem 0; }
  .frame { margin: 0; }
  figcaption {
    font: 600 12px/1.6 var(--font-sans);
    color: var(--color-text-muted);
    padding: 0 1rem 0.5rem;
  }
  /* The bar is fixed, so it has to be pinned inside its frame rather than
     escaping to the viewport -- otherwise all five render on top of each other
     at the bottom of the window and the file looks broken. This is a harness
     concern only; the component itself must stay fixed. */
  nav { position: static; }
  .frame { position: relative; border: 1px dashed var(--color-border); }
</style>
</head>
<body>
<div class="strip" style="width: 393px">${render()}</div>
</body>
</html>`

const previewDir = join(here, 'preview')
mkdirSync(previewDir, { recursive: true })
writeFileSync(join(previewDir, 'mobile-nav-light.html'), light, 'utf8')
writeFileSync(
  join(previewDir, 'mobile-nav-dark.html'),
  light.replace('<html lang="fa" dir="rtl">', '<html lang="fa" dir="rtl" class="dark">'),
  'utf8',
)

rmSync(outDir, { recursive: true, force: true })
console.log(`  ${MOBILE_NAV.length} selection states, 393px wide`)
console.log(`  open: ${previewDir}\\mobile-nav-light.html, mobile-nav-dark.html`)
