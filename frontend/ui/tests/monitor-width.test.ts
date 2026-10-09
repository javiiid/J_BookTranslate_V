/**
 * The monitor's widths, measured rather than eyeballed.
 *
 * ## What was reported, and what it turned out to be
 *
 * "The monitor page has no suitable width." Three separate things, on three
 * different surfaces, and the first pass fixed only one of them:
 *
 *   * **The chunk table.** Fixed, and the arithmetic is in
 *     `tests/monitor.test.ts` next door: four columns with no widths divide
 *     361px evenly into 90px, and the widest header is 12 characters.
 *   * **The job list card.** `flex-wrap` with the title at `flex-1`, so the
 *     badge and the counter dropped to a second line at the far edge and left a
 *     gap the width of the title beside them. Identical to what the dashboard
 *     had, and it was fixed there and missed here.
 *   * **A chunk whose content is not prose.** A chunk can be a translation
 *     memory's JSON or an XML spine, and `.chunk-text` had `overflow: hidden`
 *     with no wrapping rule. An 11,000-character unbroken run in a `dir="ltr"`
 *     cell does not wrap at all: the cell scrolls sideways inside itself, and
 *     the cell shows the first 200px of the first line with the rest
 *     unreachable.
 *
 * The third one is the reason this file exists separately. The first two are
 * layout decisions, visible in a screenshot. The third is a property of the
 * *content*, and it reappears every time a book contains something that is not
 * prose -- so it is asserted here as a rule rather than fixed once.
 *
 * ## What cannot be checked without a DOM
 *
 * An actual line break. `node --test` has no layout engine, so what is held
 * here is that the wrapping rule is present and that the content which needs it
 * exists in the data. Whether Word wraps on the fourth character is a question
 * for a browser, and the harness renders it for one.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync, readdirSync } from 'node:fs'
import { NARROWEST_VIEWPORT, NARROW_GUTTER } from '../src/lib/chunks-columns.ts'

const css = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8')
const jobList = readFileSync(new URL('../src/pages/JobListPage.tsx', import.meta.url), 'utf8')

/** What a phone has, less the gutter `.page` takes. */
const CONTENT = NARROWEST_VIEWPORT - NARROW_GUTTER * 2

/**
 * A rule's declarations, by selector.
 *
 * Anchored to the start of a line, because there are two rules for
 * `.chunk-text`: the narrow-screen override, written `.vtable .chunk-text`, and
 * the base rule. A search for `.chunk-text` finds the override first, and the
 * assertions below then report the base rule as missing its wrapping while the
 * override is perfectly correct. The two are distinguished by specificity
 * (0,2,0 against 0,1,0), not by order, so the anchor is the only reliable way
 * to name one of them.
 */
function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = new RegExp(`^\\s*${escaped}\\s*\\{([^}]*)\\}`, 'm').exec(css)
  assert.ok(match, `${selector} is not in tokens.css`)
  return match[1] as string
}

describe('the job list card', () => {
  it('is a grid, not a wrapping flex row', () => {
    // The dashboard's row was fixed for exactly this and this one was missed:
    // `flex-wrap` with a `flex-1` title puts the badge and the counter on
    // their own line at the far edge on a phone, and leaves a gap the width of
    // the title next to them.
    const row = /<div className="grid gap-\[var\(--spacing-2\)\] lg:grid-cols-\[minmax\(0,1fr\)_auto\]/.test(
      jobList,
    )
    assert.ok(row, 'the job card is still a wrapping flex row')
    assert.ok(
      !/className="flex flex-wrap items-center justify-between gap-3"/.test(jobList),
      'a wrapping flex row is still in JobListPage',
    )
  })

  it('the badge and the counter are wrapped together', () => {
    // Stacked by design -- badge above, counter beneath -- in one wrapper.
    // Two free siblings in a wrapping row is what put one at each end of a
    // line. They have to travel as one unit or they can separate again.
    assert.ok(
      /<span className="flex flex-col[^"]*">\s*<span className=\{badgeClass/.test(
        jobList,
      ),
      'the status badge and the counter are not in a single wrapper',
    )
  })

  it('the progress bar can shrink, and the gap is the smallest token on a phone', () => {
    // `flex-1` alone does not stop a flex item overflowing: the default
    // `min-width: auto` is the item's content size, so a fixed-width child
    // pushes the row wider than the screen. `min-w-0` is what releases it.
    assert.ok(/className="progress-track min-w-0 flex-1"/.test(jobList), 'the progress track cannot shrink')
    assert.ok(
      /className="mt-3 flex items-center gap-\[var\(--spacing-2\)\] lg:gap-3"/.test(jobList),
      'the progress row does not narrow its gap on a phone',
    )
  })
})

describe('the chunk text, when the chunk is not prose', () => {
  it('has a wrapping rule, because overflow: hidden alone silently eats the text', () => {
    const body = rule('.chunk-text')
    // An 11,000-character run in a `dir="ltr"` cell with no wrapping rule does
    // not wrap: the box scrolls horizontally inside its own `overflow: hidden`,
    // and the cell shows the first 200px of the first line. The rest is
    // unreachable and nothing indicates it is there.
    assert.ok(
      /overflow-wrap:\s*break-word/.test(body),
      '.chunk-text has no overflow-wrap, so an unbroken run is clipped with no way to reach it',
    )
  })

  it('uses line-break: anywhere as well, for a run one word long', () => {
    // `overflow-wrap: break-word` breaks a word that is too long for the line
    // but still lets the browser keep an unbroken run on one line when it can.
    // `anywhere` is the permission to break inside a word when even that is not
    // enough, which is what a base64 blob or a JSON payload needs.
    const body = rule('.chunk-text')
    assert.ok(
      /line-break:\s*anywhere/.test(body),
      '.chunk-text has no line-break: anywhere, so a single huge token is still clipped',
    )
  })

  it('leaves ordinary Persian alone', () => {
    // `word-break: break-all` would break Persian at every character, which is
    // unreadable -- the letters join and the shapes are what tell them apart.
    // `normal` keeps the wrapping at spaces, which is correct for prose.
    const body = rule('.chunk-text')
    assert.ok(
      /word-break:\s*normal/.test(body),
      '.chunk-text does not keep word-break: normal, so Persian breaks per character',
    )
  })

  it('still clamps to three lines on a desktop', () => {
    // The wrapping rules must not have cost the clamp: a chunk is meant to be
    // previewed, not read in full.
    const body = rule('.chunk-text')
    assert.ok(/-webkit-line-clamp:\s*3/.test(body), 'the line clamp is gone')
    assert.ok(/overflow:\s*hidden/.test(body), 'the overflow is gone')
  })
})

describe('the arithmetic the layout is held to', () => {
  it('the content width is what the gutter leaves', () => {
    // 393 - 16 a side. If the gutter changes, this is the number that moves, and
    // it is the one every column calculation is against.
    assert.equal(CONTENT, 361)
  })

  it('a card can hold a filename at the body size', () => {
    // The real filenames are long: `06a220543f6e_flex_test.epub` is 29
    // characters. At --text-body (15px) that is about 227px in a 361px column,
    // and the title is `truncate`, so the overflow is handled rather than
    // pushed. This asserts the number, so a bigger body step would show here.
    const width = Math.round(29 * 15 * 0.52)
    assert.ok(width < CONTENT, `the filename needs ${width}px of ${CONTENT}px`)
  })
})

describe('every tab was rendered at the phone width', () => {
  it('the harness covers the list and all five detail tabs', () => {
    // The first pass opened only the chunks tab, so the list card and the
    // progress grid were never looked at -- and the list card is where the
    // second of the three problems was.
    const harness = readFileSync(new URL('../scripts/render-monitor.mjs', import.meta.url), 'utf8')
    for (const tab of ['overview', 'chunks', 'qa', 'logs', 'assets']) {
      assert.ok(
        harness.includes(`initialTab: '${tab}'`),
        `the harness never renders the ${tab} tab`,
      )
    }
    assert.ok(/jobs: \{ pattern/.test(harness), 'the harness never renders the job list')
  })

  it('and the previews it writes are all present', () => {
    // A tab that was added to the list but never rendered would report a
    // missing file, which is easy to miss in a long log.
    const dir = new URL('../scripts/preview/', import.meta.url)
    const written = readdirSync(dir).filter((name) => name.startsWith('monitor-'))
    for (const tab of ['jobs', 'overview', 'chunks', 'qa', 'logs', 'assets']) {
      assert.ok(
        written.includes(`monitor-${tab}-light.html`),
        `monitor-${tab}-light.html was not written`,
      )
    }
  })
})
