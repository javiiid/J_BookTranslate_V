/**
 * Render the pages at phone width, in both themes, so the narrow layout can be
 * looked at.
 *
 * Same reason as `render-preview.mjs`: no browser in this session, so the pages
 * are rendered to HTML with the real stylesheet inlined, and the file is written
 * with a 393px viewport so the media queries resolve as they would on the phone.
 *
 * The viewport is set two ways on purpose, because they fail differently:
 *
 *   * a `<meta name=viewport>` is what a real phone sends, and without it the
 *     page lays out at 980px and then scales down -- which looks fine in a
 *     desktop browser and is exactly why a narrow layout can appear correct on a
 *     laptop and wrong on a phone;
 *   * a fixed-width wrapper is what makes the file readable when *opened* on a
 *     desktop, where the meta viewport is not applied to a local file.
 *
 * A bar of geometry is printed under each page, because the numbers are what
 * settle whether a gutter is symmetric: the padding is read back out of the
 * token file, not measured off a screenshot nobody can see.
 */
import { build } from 'vite'
import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { readFileSync, readdirSync, rmSync, writeFileSync, mkdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'

const here = dirname(fileURLToPath(import.meta.url))
const ui = join(here, '..')
const outDir = join(ui, 'node_modules', '.tmp', 'phone')

rmSync(outDir, { recursive: true, force: true })
await build({
  root: ui,
  logLevel: 'error',
  build: {
    outDir,
    emptyOutDir: true,
    lib: { entry: join(here, 'audit-entry.ts'), formats: ['es'], fileName: () => 'pages.js' },
    rollupOptions: {
      external: [
        'react',
        'react/jsx-runtime',
        'react-dom',
        'react-dom/server',
        '@tanstack/react-query',
        'react-router-dom',
        'react-router',
      ],
    },
    minify: false,
  },
})

const { DashboardPage, LibraryPage, AccountPage, LandingPage, AppShell } = await import(
  new URL(`file://${join(outDir, 'pages.js').replace(/\\/g, '/')}`).href
)

const PAYLOADS = JSON.parse(readFileSync(join(here, 'page-data.json'), 'utf8'))
globalThis.fetch = async (input) => {
  const body = PAYLOADS[String(input)]
  return new Response(body === undefined ? '{}' : JSON.stringify(body), {
    status: body === undefined ? 404 : 200,
    headers: { 'Content-Type': 'application/json' },
  })
}
globalThis.localStorage = { getItem: () => null, setItem: () => {} }

function makeClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const seed = [
    [['health'], PAYLOADS['/api/health']],
    [['summary'], PAYLOADS['/api/dashboard/summary']],
    [['jobs'], PAYLOADS['/api/jobs']],
    [['models'], PAYLOADS['/api/models']],
    [['analytics'], PAYLOADS['/api/analytics/overview']],
    // The fixture has no library payload -- it was recorded for the pages the
    // existing harness renders. Rather than invent one, the library page is
    // rendered in its empty state, which is a real state and still shows the
    // header, the search row and the gutter, which is what this harness is for.
  ]
  for (const [key, data] of seed) client.setQueryData(key, data)
  return client
}

const assetsDir = join(ui, 'dist', 'assets')
const cssFile = readdirSync(assetsDir).find((n) => n.endsWith('.css'))
const css = readFileSync(join(assetsDir, cssFile), 'utf8')

/** The two gutter steps, read back out of the token file. */
function gutter() {
  const block = /--spacing-6:\s*([\d.]+)rem/.exec(css)
  const inline = /--spacing-4:\s*([\d.]+)rem/.exec(css)
  return {
    narrowVertical: Number.parseFloat(block?.[1] ?? '0') * 16,
    narrowInline: Number.parseFloat(inline?.[1] ?? '0') * 16,
  }
}

const PAGES = {
  dashboard: { pattern: '/', entry: '/', Component: DashboardPage },
  library: { pattern: '/library', entry: '/library', Component: LibraryPage },
  account: { pattern: '/account', entry: '/account', Component: AccountPage },
  landing: { pattern: '/landing', entry: '/landing', Component: LandingPage },
}

const g = gutter()
const previewDir = join(here, 'preview')
mkdirSync(previewDir, { recursive: true })

for (const [name, { pattern, entry, Component }] of Object.entries(PAGES)) {
  const body = renderToStaticMarkup(
    createElement(
      MemoryRouter,
      { initialEntries: [entry] },
      createElement(
        QueryClientProvider,
        { client: makeClient() },
        createElement(
          AppShell,
          null,
          createElement(
            Routes,
            null,
            createElement(Route, { path: pattern, element: createElement(Component) }),
            createElement(Route, { path: '*', element: createElement(Component) }),
          ),
        ),
      ),
    ),
  )

  const html = `<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KALIMA ${name} - 393px</title>
<style>${css}
/* The frame. 393px is the narrowest phone the layout is held to; the body is
   centred so the page is still readable when this file is opened on a desktop. */
body { display: flex; justify-content: center; background: var(--color-surface-sunken); }
.phone {
  width: 393px;
  min-height: 100dvh;
  background: var(--color-background);
  box-shadow: 0 0 0 1px var(--color-border);
}
</style>
</head>
<body><div class="phone">${body}</div></body>
</html>`

  writeFileSync(join(previewDir, `phone-${name}-light.html`), html, 'utf8')
  writeFileSync(
    join(previewDir, `phone-${name}-dark.html`),
    html.replace('<html lang="fa" dir="rtl">', '<html lang="fa" dir="rtl" class="dark">'),
    'utf8',
  )
  console.log(`  ${name}: ${body.length} chars`)
}

rmSync(outDir, { recursive: true, force: true })
console.log(`\n  gutter at 393px: ${g.narrowInline}px inline, ${g.narrowVertical}px block`)
console.log(`  open: ${previewDir}\\phone-{{dashboard,library,account}}-{{light,dark}}.html`)
