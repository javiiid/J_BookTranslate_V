/**
 * The frontend is the whole UI. The backend is an API.
 *
 * ## The complaint
 *
 * "It keeps popping up in the frontend" -- twice, for two different reasons.
 *
 * The first was Fast Refresh, and it is in `fast-refresh.test.ts`.
 *
 * This one is the routing. `vite.config.ts` proxied six bare paths to the Python
 * backend: `/reader`, `/library`, `/account`, `/workspace`, `/landing`,
 * `/welcome`. Five of those are React routes, and the backend answers four of
 * them with a server-rendered HTML page. Vite's proxy runs *before* its own SPA
 * fallback, so whichever matched first won:
 *
 *   * `/landing` returned 65,100 bytes of Python HTML with no React on it, so
 *     visiting it left the app completely;
 *   * `/library`, `/account` and `/workspace` were forwarded to a handler that
 *     returns `text/html` where the client expected a module.
 *
 * Measured, not inferred: a request to `http://<lan>:5173/landing` came back
 * with 65,100 bytes and no `<div id="root">`, while `/` came back with 989 bytes
 * and one.
 *
 * ## What this holds
 *
 * Every proxy target is under `/api` or `/downloads`, and every React route
 * resolves inside the client. The second half matters as much as the first: a
 * narrowed proxy is only correct if nothing was relying on the old behaviour,
 * and `/landing` was relying on it by redirecting rather than rendering.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { existsSync, readFileSync } from 'node:fs'

const configUrl = new URL('../vite.config.ts', import.meta.url)
const appUrl = new URL('../src/App.tsx', import.meta.url)
const config = readFileSync(configUrl, 'utf8')
const app = readFileSync(appUrl, 'utf8')

/** The proxy block, as a string. */
function proxyBlock(): string {
  const start = config.indexOf('proxy:')
  assert.notEqual(start, -1, 'vite.config.ts has no proxy block')
  const open = config.indexOf('{', start)
  let depth = 0
  for (let i = open; i < config.length; i++) {
    if (config[i] === '{') depth++
    if (config[i] === '}') {
      depth--
      if (depth === 0) return config.slice(open, i + 1)
    }
  }
  return config.slice(open)
}

describe('nothing but the API is proxied', () => {
  /**
   * The paths that may be proxied to the backend.
   *
   * `/api` and `/downloads` are the API, and `/covers` is the backend's
   * cover-image route (`GET /covers/<id>.<ext>` out of `data/covers`).
   * `/reader` is the one deliberate exception and it is listed separately
   * below, so that adding a second exception has to mean changing this list
   * on purpose rather than by appending a line to the config.
   */
  const API_PREFIXES = ['/api', '/downloads', '/covers']
  /** `/reader` stays listed because chapter images still come from the
   *  backend — but only through the `bypass` rule (page → SPA shell,
   *  `/reader/<id>/asset/*` → backend). It is no longer a page handover,
   *  so the suite below pins both halves instead of a temporary exception. */
  const EXCEPTIONS = ['/reader']

  it('every proxy key is the API or a named exception', () => {
    const block = proxyBlock()
    const keys = [...block.matchAll(/['"](\/[^'"]*)['"]\s*:/g)].map((m) => m[1] as string)
    assert.ok(keys.length > 0, 'the proxy block is empty')
    const bad = keys.filter(
      (key) => ![...API_PREFIXES, ...EXCEPTIONS].some((allowed) => key === allowed),
    )
    assert.deepEqual(
      bad,
      [],
      `these paths are proxied to the backend and would shadow a React route: ${bad.join(', ')}`,
    )
  })

  it('the five paths that must never come back are still gone', () => {
    const block = proxyBlock()
    for (const path of ['/library', '/account', '/workspace', '/landing', '/welcome']) {
      assert.ok(
        !block.includes(`'${path}'`),
        `${path} is proxied again; the backend serves it as HTML, so it wins over the SPA`,
      )
    }
  })

  it('/api and /downloads are still proxied', () => {
    // The narrowing must not have taken the API with it -- the whole frontend
    // fetches through it, and every call is a relative path.
    const block = proxyBlock()
    assert.ok(block.includes("'/api'"), '/api is no longer proxied')
    assert.ok(block.includes("'/downloads'"), '/downloads is no longer proxied')
  })

  it('the /reader rule is assets-only, with a bypass for the page', () => {
    // The chapter HTML the API returns carries image URLs shaped
    // `/reader/<id>/asset/<path>`, and those bytes only exist on the backend.
    // The page itself belongs to the client router, so the rule must say
    // `bypass` (page URLs answer the SPA shell) and name `/asset/` (image
    // URLs proxy through). A blanket `/reader` target would shadow the React
    // route again -- that was the handover this replaces.
    const block = proxyBlock()
    assert.ok(block.includes("'/reader'"), 'the /reader asset rule is gone; chapter images break in dev')
    assert.ok(block.includes('bypass'), 'the /reader rule has no bypass, so it shadows the React route')
    // The rule names the path as a regex (`/\/asset\//`), so the assertion
    // looks for `/asset` rather than the quoted prefix.
    assert.ok(block.includes('/asset'), 'the /reader rule does not name the asset URLs it must let through')
  })
})

describe('the reader belongs to React', () => {
  /**
   * The React port finished its P0 (settings, glossary panel, paragraph
   * pairing, columns mode), so `/reader/:id` renders `ReaderPage` and the
   * Python handover is closed. Asserted in three directions: the route is
   * mounted, no placeholder intercepts it, and the chapter images that still
   * live on the backend keep working through the `bypass` rule.
   */

  it('the route mounts the React reader', () => {
    assert.ok(
      /path="\/reader\/:id"\s+element=\{<\s*ReaderPage\s*\/>\s*\}/.test(app),
      '/reader/:id does not render ReaderPage',
    )
  })

  it('no handover placeholder intercepts the route', () => {
    assert.ok(
      !/ReaderHandedOver/.test(app),
      'ReaderHandedOver is still mounted, so the React port never runs',
    )
  })

  it('the React port is on disk and exported', () => {
    const source = readFileSync(new URL('../src/pages/ReaderPage.tsx', import.meta.url), 'utf8')
    assert.match(source, /export function ReaderPage\(/, 'the React reader is gone')
    // A route that names a component that was never written renders nothing;
    // `npm run typecheck` would catch that, but the assertion here names it.
    assert.ok(
      readFileSync(new URL('../src/components/AppShell.tsx', import.meta.url), 'utf8').length > 0,
      'AppShell is missing, so the port renders outside the shared chrome',
    )
  })

  it('reader links stay inside the SPA', () => {
    // A plain anchor to `/reader/<id>` reloads the whole app; `<Link>`
    // keeps the settings query warm. The library, the dashboard and the
    // monitor all link to the reader, so all three are pinned here.
    for (const file of [
      '../src/pages/LibraryPage.tsx',
      '../src/pages/DashboardPage.tsx',
      '../src/components/monitor/OverviewTab.tsx',
    ]) {
      const source = readFileSync(new URL(file, import.meta.url), 'utf8')
      assert.ok(
        !/<a[^>]*href=\{(readable\.reader|last\.variant\.reader|lastReadable\.reader|job\.reader)\}/.test(source),
        `${file} links to the reader with a plain anchor instead of <Link>`,
      )
    }
  })
})

describe('every React route renders a React page', () => {
  it('no route redirects away, because a redirect was the workaround for the proxy', () => {
    // `/landing` used to be `<Navigate to="/" replace />` -- the app pretending
    // the path did not exist because it was being served by something else.
    assert.ok(
      !/element=\{<Navigate/.test(app),
      'a route still redirects; that was the workaround for the shadowed path',
    )
  })

  it('every Route element is a page component, not a redirect', () => {
    // The whitespace inside `element={<X />}` varies with formatting, so the
    // pattern allows any run of it. The first version demanded exactly one
    // space and matched nothing, then reported "the walk is suspect" about a
    // file that has nine routes.
    const elements = [
      ...app.matchAll(/<Route\s+path="([^"]+)"\s+element=\{<\s*(\w+)\s*\/>\s*\}/g),
    ]
    assert.ok(elements.length >= 9, `only found ${elements.length} routes; the walk is suspect`)
    for (const match of elements) {
      // noUncheckedIndexedAccess: a group is `string | undefined`, and handing
      // that to assert.match is a type error rather than a helpful message.
      const path = match[1] ?? ''
      const component = match[2] ?? ''
      assert.notEqual(component, 'Navigate', `${path} renders a Navigate`)
      assert.match(component, /Page$/, `${path} renders ${component}, which is not a page`)
    }
  })

  it('the workshop route is mounted, because intake navigates to it', () => {
    // `/workspace` now opens a calibration workshop and redirects there. A route
    // that was missing made the redirect land on the catch-all, so a freshly
    // uploaded book appeared to vanish with no error anywhere.
    assert.match(
      app,
      /path="\/calibrations\/:id"\s+element=\{<\s*CalibrationPage\s*\/>\s*\}/,
      '/calibrations/:id is not routed, so the workspace redirect lands on the 404 page',
    )
  })

  it('the workshop page exists on disk', () => {
    const page = new URL('../src/pages/CalibrationPage.tsx', import.meta.url)
    assert.ok(existsSync(page), 'CalibrationPage.tsx is missing; the route above renders nothing')
  })

  it('/landing renders a page that exists on disk', () => {
    // A route can name a component that was never written; `npm run typecheck`
    // would catch that, but the assertion here names the failure.
    assert.ok(
      /path="\/landing"\s+element=\{<\s*LandingPage\s*\/>\s*\}/.test(app),
      '/landing is not routed to LandingPage',
    )
    const source = readFileSync(new URL('../src/pages/LandingPage.tsx', import.meta.url), 'utf8')
    assert.ok(
      /export function LandingPage\(/.test(source),
      'LandingPage.tsx does not export LandingPage',
    )
  })

  it('the landing page uses the shared chrome rather than its own header', () => {
    // A marketing page that reinvents the shell is how the two halves of the app
    // start to look like different products.
    const source = readFileSync(new URL('../src/pages/LandingPage.tsx', import.meta.url), 'utf8')
    assert.ok(/from '@\/components\/AppShell'/.test(source), 'LandingPage does not use the shared chrome')
    assert.ok(/className="page"/.test(source), 'LandingPage does not use the .page gutter')
  })
})

describe('the app fetches through relative paths only', () => {
  it('no fetch or api call names an absolute host', () => {
    // An absolute URL would bypass the proxy and hit 127.0.0.1, which is the
    // laptop and not the phone. This is the other half of why only /api is
    // proxied: the client has to reach the backend *through* the dev server.
    const files = ['../src/lib/api.ts', '../src/lib/conversion.ts', '../src/lib/chunks.ts']
    const offenders: string[] = []
    for (const file of files) {
      const source = readFileSync(new URL(file, import.meta.url), 'utf8')
      for (const [index, line] of source.split('\n').entries()) {
        if (!/\bfetch\(/.test(line)) continue
        if (/https?:\/\//.test(line)) {
          offenders.push(`${file}:${index + 1}  ${line.trim().slice(0, 80)}`)
        }
      }
    }
    assert.deepEqual(offenders, [], `an absolute URL bypasses the proxy:\n  ${offenders.join('\n  ')}`)
  })
})
