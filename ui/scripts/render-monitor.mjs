/**
 * Render the monitor at phone width, in both themes.
 *
 * The job list and the job detail page are the widest surfaces in the app: a
 * four-column table of chunks, a filter row, and a progress grid. They are
 * measured here at 393px because that is where they break, and a screenshot
 * nobody can take is not evidence.
 *
 * The chunk table is the one to watch. It is `table-layout: fixed` with four
 * columns and no widths, so the browser divides the available width evenly --
 * about 90px a column at 393px. A Persian word does not fit in 90px, so the
 * chunk text wraps to three lines and the row grows past the height the
 * virtualiser assumed, and the scroll window and the rendered rows disagree.
 * That is the "the monitor has no suitable width" report, and it is a width
 * problem before it is a table problem.
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
const outDir = join(ui, 'node_modules', '.tmp', 'monitor')

rmSync(outDir, { recursive: true, force: true })
await build({
  root: ui,
  logLevel: 'error',
  build: {
    outDir,
    emptyOutDir: true,
    lib: { entry: join(here, 'monitor-entry.ts'), formats: ['es'], fileName: () => 'monitor.js' },
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

const { JobListPage, JobDetailPage, AppShell } = await import(
  new URL(`file://${join(outDir, 'monitor.js').replace(/\\/g, '/')}`).href
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

const JOB_ID = '040061b0658b'

function makeClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const seed = [
    [['health'], PAYLOADS['/api/health']],
    [['jobs'], PAYLOADS['/api/jobs']],
    [['job', JOB_ID], PAYLOADS[`/api/jobs/${JOB_ID}`]],
    // The key is `job-chunks`, not `chunks`: JobDetailPage fetches it under
    // that key and passes the rows down as a prop, so seeding the wrong one
    // leaves the table empty and the harness reporting "0 table columns" --
    // which reads as a layout problem and is a fixture problem.
    [['job-chunks', JOB_ID], PAYLOADS[`/api/jobs/${JOB_ID}/chunks`]],
  ]
  for (const [key, data] of seed) client.setQueryData(key, data)
  return client
}

const assetsDir = join(ui, 'dist', 'assets')
const cssFile = readdirSync(assetsDir).find((n) => n.endsWith('.css'))
const css = readFileSync(join(assetsDir, cssFile), 'utf8')

/** Column widths the browser gives each cell at this viewport. */
function columnWidths(columnCount, viewport) {
  // The table is width:100% with table-layout:fixed and no column widths, so
  // the space divides evenly and the border takes a pixel or two.
  return Math.floor(viewport / columnCount)
}

const NARROWEST = 393
const PAGES = {
  jobs: { pattern: '/jobs', entry: '/jobs', Component: JobListPage },
  // The chunk table is the widest surface in the app and it lives behind the
  // chunks tab, so the harness opens that tab rather than the overview. A
  // layout that is only visible after a click is a layout nobody checks.
  overview: {
    pattern: '/jobs/:id',
    entry: `/jobs/${JOB_ID}`,
    Component: JobDetailPage,
    props: { initialTab: 'overview' },
  },
  chunks: {
    pattern: '/jobs/:id',
    entry: `/jobs/${JOB_ID}`,
    Component: JobDetailPage,
    props: { initialTab: 'chunks' },
  },
  qa: {
    pattern: '/jobs/:id',
    entry: `/jobs/${JOB_ID}`,
    Component: JobDetailPage,
    props: { initialTab: 'qa' },
  },
  logs: {
    pattern: '/jobs/:id',
    entry: `/jobs/${JOB_ID}`,
    Component: JobDetailPage,
    props: { initialTab: 'logs' },
  },
  assets: {
    pattern: '/jobs/:id',
    entry: `/jobs/${JOB_ID}`,
    Component: JobDetailPage,
    props: { initialTab: 'assets' },
  },
}

const previewDir = join(here, 'preview')
mkdirSync(previewDir, { recursive: true })

for (const [name, { pattern, entry, Component, props }] of Object.entries(PAGES)) {
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
            createElement(Route, { path: pattern, element: createElement(Component, props) }),
            createElement(Route, { path: '*', element: createElement(Component, props) }),
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
<title>KALIMA ${name} - ${NARROWEST}px</title>
<style>${css}
body { display: flex; justify-content: center; background: var(--color-surface-sunken); }
.phone {
  width: ${NARROWEST}px;
  min-height: 100dvh;
  background: var(--color-background);
  box-shadow: 0 0 0 1px var(--color-border);
}
</style>
</head>
<body><div class="phone">${body}</div></body>
</html>`

  writeFileSync(join(previewDir, `monitor-${name}-light.html`), html, 'utf8')
  writeFileSync(
    join(previewDir, `monitor-${name}-dark.html`),
    html.replace('<html lang="fa" dir="rtl">', '<html lang="fa" dir="rtl" class="dark">'),
    'utf8',
  )

  // What the widths come to, so the numbers are reported rather than guessed.
  const columns = (body.match(/<th scope="col">/g) ?? []).length
  const per = columns > 0 ? columnWidths(columns, NARROWEST) : null
  console.log(
    `  ${name}: ${body.length} chars, ${columns} table columns` +
      (per ? `, ${per}px each at ${NARROWEST}px` : ', no table'),
  )
}

rmSync(outDir, { recursive: true, force: true })
console.log(`\n  open: ${previewDir}\\monitor-{{jobs,detail}}-{{light,dark}}.html`)
