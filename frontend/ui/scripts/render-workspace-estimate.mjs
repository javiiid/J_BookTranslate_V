/**
 * Render the estimate dialog with real data, and assert it is in the markup.
 *
 * The complaint that started this was "nothing shows up", and the cause was that
 * the dialog was gated on a path nothing ever set -- so it never opened and a
 * render of the page proved nothing. This forces the open state, seeds the
 * estimate from a payload captured off the live server, and then checks the
 * rendered HTML for the things a reader would look for: the three cards, the real
 * numbers, the footer, and a primary button that is not disabled.
 *
 * Two variants, because the dialog has two branches that matter: a known price,
 * and no price on file. The second is the one that must not print a zero.
 */
import { build } from 'vite'
import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync, readdirSync, rmSync, mkdirSync, writeFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'

const here = dirname(fileURLToPath(import.meta.url))
const ui = join(here, '..')
const outDir = join(ui, 'node_modules', '.tmp', 'estimate')

rmSync(outDir, { recursive: true, force: true })
await build({
  root: ui,
  logLevel: 'error',
  build: {
    outDir,
    emptyOutDir: true,
    lib: { entry: join(here, 'audit-entry.ts'), formats: ['es'], fileName: () => 'pages.js' },
    rollupOptions: {
      external: ['react', 'react/jsx-runtime', 'react-dom', 'react-dom/server', '@tanstack/react-query', 'react-router-dom', 'react-router'],
    },
    minify: false,
  },
})

const { EstimateModal } = await import(
  new URL(`file://${join(outDir, 'pages.js').replace(/\\/g, '/')}`).href
)

const PAYLOADS = JSON.parse(readFileSync(join(here, 'page-data.json'), 'utf8'))

/* The request the dialog was captured making. It lives beside the payload it
   produced, and the payload is rewritten whenever the estimator changes -- so it
   is stored under its own key rather than as a field of the response, where
   regenerating the response silently drops the request that generated it. That
   is what happened once, and the failure was `REQUEST.file_path` on undefined. */
const REQUEST =
  PAYLOADS['/api/jobs/estimate/__request__'] ??
  PAYLOADS['/api/jobs/estimate'].__request__ ??
  {
    file_path: '2de7e9f4032e_overthesevensea.epub',
    model: 'gemini-3.1-flash-lite',
    mode: 'fast',
    concurrency: 12,
  }

/* The dialog fetches by URL, so the stub answers on the request the dialog makes. */
globalThis.fetch = async (input) => {
  const url = String(input)
  if (url === '/api/jobs/estimate') {
    const model = REQUEST.model
    const body =
      model === 'gpt-9-imaginary'
        ? PAYLOADS['/api/jobs/estimate/unknown-model']
        : PAYLOADS['/api/jobs/estimate']
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const body = PAYLOADS[url]
  return new Response(body === undefined ? '{}' : JSON.stringify(body), {
    status: body === undefined ? 404 : 200,
    headers: { 'Content-Type': 'application/json' },
  })
}
globalThis.localStorage = { getItem: () => null, setItem: () => {} }

const REQUEST_KEY = JSON.stringify({
  filePath: REQUEST.file_path,
  request: {
    model: REQUEST.model,
    mode: REQUEST.mode,
    concurrency: REQUEST.concurrency,
    glossary_auto: false,
    from_lang: 'EN',
    to_lang: 'FA',
  },
})

function render(estimate) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } },
  })
  // The dialog reads its data through useQuery, so the cache is seeded exactly
  // the way react-query would key it.
  client.setQueryData(['estimate', REQUEST.file_path, JSON.parse(REQUEST_KEY).request], estimate)
  return renderToStaticMarkup(
    createElement(
      MemoryRouter,
      { initialEntries: ['/workspace'] },
      createElement(
        QueryClientProvider,
        { client },
        createElement(
          EstimateModal,
          {
            open: true,
            onClose: () => {},
            filePath: REQUEST.file_path,
            bookTitle: 'Hands-On_Large_Language_Models_FA.epub',
            request: JSON.parse(REQUEST_KEY).request,
            starting: false,
            onStart: () => {},
          },
          null,
        ),
      ),
    ),
  )
}

const known = PAYLOADS['/api/jobs/estimate']
const unknown = PAYLOADS['/api/jobs/estimate/unknown-model']
const resumed = PAYLOADS['/api/jobs/estimate/resume']

const failures = []
function check(label, ok, detail = '') {
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${label}${detail ? `  ${detail}` : ''}`)
  if (!ok) failures.push(label)
}

console.log('=== the dialog, with a known price ===')
const html = render(known)
console.log(`  rendered ${html.length} chars`)

check('the dialog is present', html.includes('role="dialog"'))
check('aria-modal is set', html.includes('aria-modal="true"'))
check('the title is there', html.includes('تخمین هزینه و زمان'))
check('the book name is shown', html.includes('Hands-On'))
check('the cost is a range', /\$\d+\.\d\d\s*–\s*\$/.test(html), html.match(/\$\d+\.\d\d[^<]*/)?.[0] ?? '')
check('the token count is shown', html.includes(String(known.token_count).replace(/\B(?=(\d{3})+(?!\d))/g, ',').replace(/,/g, '٬')) || /توکن/.test(html))
check('the duration is shown', html.includes(known.estimated_time), known.estimated_time)
check('the chunk figure is shown', /بخش/.test(html))
// Persian digits: the component runs the number through `fa()`, so the rendered
// text is ۱۲ and never "12". Checking for the Latin form would pass on a
// component that forgot to localise, which is the thing worth catching.
check(
  'the concurrency is shown, in Persian digits',
  html.includes('۱۲') && /رشتهٔ موازی/.test(html),
  '۱۲',
)
check('the process summary lists the model', html.includes(known.model))
check('the process summary lists the mode', /حالت/.test(html))
check('the language pair is listed', /زبان مبدأ/.test(html) && /زبان مقصد/.test(html))
check('the primary button is enabled', !/disabled[^>]*>شروع ترجمه/.test(html))
check('the primary button says start', html.includes('شروع ترجمه'))
check('cancel is present', html.includes('انصراف'))
check('the settings button is present', /تنظیمات/.test(html))
check('the steps toggle is present', html.includes('جزئیات فرایند'))
check('no resume banner without a checkpoint', !html.includes('ترجمهٔ ناتمام'))
check('a closing button exists', /aria-label="بستن"/.test(html))

console.log('')
console.log('=== the dialog, with no price on file ===')
const html2 = render(unknown)
check('it renders rather than failing', html2.includes('role="dialog"'))
check('it says the price is unknown', html2.includes('نامشخص'), 'نامشخص')
check('it says no price is on file', html2.includes('قیمتی ثبت نشده'))
check(
  'it does NOT print $0.00 as the cost',
  !/\$\s*0\.00\s*–/.test(html2),
  'a zero reads as free, which is the bug this replaces',
)
check('the primary button is still enabled', !/disabled[^>]*>شروع ترجمه/.test(html2))

console.log('')
console.log('=== the total, and the parts that explain it ===')
/* The badge this replaces.

   `cost_for` added the glossary to the base before applying the band, so the
   headline already contained it -- and the dialog then printed a badge reading
   "شامل واژه‌نامه +$0.12" underneath. A reader who believed the "+" added
   $0.12 to a total that had it in already. The word said "شامل" (includes) and
   the sign said "+" (add); they contradicted each other, and the reader was right
   to distrust the figure.
 */
const cost = known.estimated_cost
check('the two parts are shown', /ترجمه/.test(html) && /واژه‌نامه/.test(html))
check('the sum is shown', /جمع/.test(html))
check(
  'the parts visibly add up to the sum',
  (() => {
    const shown = (v) => Number(v.toFixed(2))
    return Math.abs(shown(cost.translation) + shown(cost.glossary) - shown(cost.base)) < 0.005
  })(),
  `${cost.translation.toFixed(2)} + ${cost.glossary.toFixed(2)} = ${(
    cost.translation + cost.glossary
  ).toFixed(4)}, base ${cost.base}`,
)
check(
  'the parts and the sum actually rendered',
  html.includes(`$${cost.translation.toFixed(2)}`) &&
    html.includes(`$${cost.glossary.toFixed(2)}`) &&
    html.includes(`$${cost.base.toFixed(2)}`),
)
check(
  'no "+$" surcharge beside the total',
  !/\+\s*\$\s*[\d.]+\s*شامل/.test(html) && !/شامل واژه‌نامه\s*\+/.test(html),
  'the glossary is a part of the total, not an addition to it',
)
check('no glossary badge remains', !/شامل واژه‌نامه/.test(html))

console.log('')
console.log('=== bidi: the numbers must not reorder ===')
/* Measured with python-bidi: in an RTL paragraph, "شامل واژه‌نامه +$0.12" comes out
   of the layout as "0.12$+" -- the plus sign on the far side of the number from
   the dollar. An LTR isolate keeps it as written. `<bdi>` is the cheapest way to
   get one, so the check is that the isolate is in the markup.

   The range `$0.15 – $0.20` needed no fix: reordered it reads right-to-left with
   the smaller number first, which is what a Persian reader expects of a range.
 */
const bdiCount = (html.match(/<bdi>/g) ?? []).length
check('numeric runs are isolated with <bdi>', bdiCount > 0, `${bdiCount} isolate(s)`)
check(
  'every dollar amount is inside an isolate',
  (() => {
    // Walk the markup and make sure no `$` sits outside a <bdi>...</bdi> run.
    const withoutIsolates = html.replace(/<bdi>.*?<\/bdi>/g, '')
    return !withoutIsolates.includes('$')
  })(),
  'a bare $ outside an isolate is what the bidi algorithm reorders',
)

console.log('')
console.log('=== a part-finished book ===')
/* `resume_for` read `find_resumable_jobs`' output as dictionaries when it yields
   `(name, timestamp, state)` tuples, so every job was silently discarded and
   `resume_progress` was always null. Nothing compared completed against total, so
   a book translated the day before came back as resumable -- and was then priced
   as if all 60 chunks were about to be sent, next to a button reading "continue
   where it left off".
 */
const html3 = render(resumed)
check('it renders', html3.includes('role="dialog"'))
check('the resume banner is there', html3.includes('ترجمهٔ ناتمام'))
check(
  'nothing rendered as [object Object]',
  ![html, html2, html3].some((h) => h.includes('[object Object]')),
  'a React element interpolated into a template string -- the isolate worked, around the wrong content',
)
check(
  'the progress is shown, not a bare "found one"',
  html3.includes(`${Math.round(resumed.resume_progress * 100).toLocaleString('fa-IR')}٪`),
  `${Math.round(resumed.resume_progress * 100)}%`,
)
check('the remaining count is stated', /بخش\s*باقی‌مانده/.test(html3))
check('it says the done chunks are not resent', /دوباره فرستاده نمی‌شود/.test(html3))
check('the cost card is labelled as the remainder', html3.includes('هزینهٔ باقی‌مانده'))
check('the time card is labelled as the remainder', html3.includes('زمان باقی‌مانده'))
check(
  'the billable chunk count is the small one, in Persian digits',
  // Matched against the text with the tags stripped and the whitespace
  // collapsed, because the figure is inside a <bdi> and JSX indentation puts
  // arbitrary newlines between the words. Asserting on a raw substring here
  // tests the formatting, not the number.
  (() => {
    // Scoped to the time card. The whole-book count legitimately appears in the
    // resume banner -- "88% of 60 chunks are saved" -- so a page-wide check for
    // it would fail on correct output. What must not happen is the time card
    // quoting the whole book while the button offers to continue.
    const card = html3.match(/زمان باقی‌مانده<\/span>.*?<\/div>/s)
    if (!card) return false
    const text = card[0].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
    const wanted = new Intl.NumberFormat('fa-IR').format(resumed.chunk_count)
    const whole = new Intl.NumberFormat('fa-IR').format(resumed.chunk_count_total)
    return text.includes(`${wanted} بخش`) && !text.includes(`${whole} بخش`)
  })(),
  `${resumed.chunk_count} billable of ${resumed.chunk_count_total}`,
)
check(
  'the total is for the remainder, not the whole book',
  html3.includes(`$${resumed.estimated_cost.max.toFixed(2)}`) &&
    !html3.includes(`$${cost.max.toFixed(2)}`),
  `remainder max $${resumed.estimated_cost.max}, whole book max $${cost.max}`,
)

console.log('')
console.log('=== a sub-cent remainder must not print $0.00 ===')
/* Resuming bills only what is left, and the remainder is often worth a few cents.
   Four chunks of the cheapest model cost about $0.0024, which at two decimals is
   "$0.00" -- the one string this feature exists to keep off the page, because a
   zero beside a "start translating" button reads as free. */
const cheap = {
  ...resumed,
  chunk_count: 4,
  chunk_count_total: 17,
  chunks_already_done: 13,
  resume_progress: 13 / 17,
  resume_remaining: 4,
  token_count: 4000,
  estimated_cost: {
    min: 0.002,
    max: 0.0028,
    base: 0.0024,
    translation: 0.0024,
    glossary: 0,
    currency: 'USD',
    known: true,
  },
  glossary_cost: 0,
}
const html4 = render(cheap)
const text4 = html4.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
check('a sub-cent amount keeps its digits', text4.includes('$0.0024'), 'expected $0.0024')
check(
  'no amount is printed as a bare $0.00',
  // Anchored with a word boundary at the end. A plain substring test for '$0.00'
  // fails on the correct output, because '$0.0020' contains '$0.00' -- which is
  // what the first version of this check did, and it flagged correct markup.
  !/\$0\.00(?!\d)/.test(text4),
  'a zero reads as free, which is the bug this replaces',
)
check(
  'the range keeps both ends at four decimals',
  text4.includes('$0.0020') && text4.includes('$0.0028'),
)
check('the remaining count is still shown', text4.includes('۴ بخش'))

console.log('')
console.log(`=== ${failures.length === 0 ? 'all checks pass' : `${failures.length} FAILED`} ===`)
for (const name of failures) console.log(`  - ${name}`)

const previewDir = join(here, 'preview')
mkdirSync(previewDir, { recursive: true })
const assets = readdirSync(join(ui, 'dist', 'assets'))
const css = readFileSync(join(ui, 'dist', 'assets', assets.find((n) => n.endsWith('.css'))), 'utf8')
for (const [name, markup] of [
  ['estimate-known', html],
  ['estimate-unknown', html2],
  ['estimate-resume', html3],
  ['estimate-sub-cent', html4],
]) {
  writeFileSync(
    join(previewDir, `${name}.html`),
    `<!doctype html>\n<html lang="fa" dir="rtl">\n<head><meta charset="utf-8">\n<title>KALIMA — ${name}</title>\n<style>${css}</style>\n</head>\n<body>${markup}</body>\n</html>`,
    'utf8',
  )
}
console.log(`  previews written to ${previewDir}`)

rmSync(outDir, { recursive: true, force: true })
process.exit(failures.length === 0 ? 0 : 1)
