/**
 * The chunk table, and the width arithmetic behind it.
 *
 * ## The complaint
 *
 * "The monitor has no suitable width." Measured at 393px with the `.page`
 * gutter, the table gets 361px. It is `table-layout: fixed` with four columns
 * and no widths, so the browser divides that evenly: **90px a column**. A
 * Persian word at 14px is about 10 characters in 90px, and the widest header
 * the table carries -- `ترجمهٔ نهایی` -- is 14 characters. The header wrapped,
 * the row grew past the 96px the virtualiser assumes, and the scroll window and
 * the rendered rows drifted apart.
 *
 * ## Why the fix is a reflow and not a column width
 *
 * No column width makes a four-column table readable at 90px a column. So below
 * 640px the table becomes a stack of labelled blocks. A horizontal scroll on a
 * phone hides data behind a gesture, and a monitoring table is read by looking
 * down a column.
 *
 * That reflow needs each cell to carry its own label, because a stacked cell has
 * no header above it. The labels live in `CHUNK_COLUMNS` and the `th` text is
 * read from the same declaration, so the two cannot drift.
 *
 * ## The thing that was silently un-overridable
 *
 * The widths were inline `style` on every `td`. An inline style beats a class at
 * any specificity, so the mobile rules in `tokens.css` could never have applied
 * -- the table was authored to be exactly as un-overridable as it needed to be
 * overridable. The widths and the labels are now in one exported constant, and
 * the tests below hold that the table has no inline width of its own.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync, readdirSync } from 'node:fs'
import { ROW_H, OVERSCAN, computeWindow } from '../src/lib/virtual.ts'
import {
  CHUNK_COLUMNS,
  CHUNK_COLUMN_LIST,
  NARROWEST_VIEWPORT,
  PX_PER_CHARACTER_AT_12PX,
  evenSplit,
} from '../src/lib/chunks-columns.ts'

const css = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8')
const table = readFileSync(
  new URL('../src/components/monitor/VirtualChunkTable.tsx', import.meta.url),
  'utf8',
)

/**
 * The body of the reflow block in the *built* stylesheet, by brace counting.
 *
 * Two things this has to get right, both learned by getting them wrong:
 *
 *   * **Brace counting, not a regex.** A pattern ending at the first `\n  }`
 *     stops inside the block, because it is nine rules deep.
 *   * **Range syntax, not `max-width`.** The minifier rewrites
 *     `@media (max-width: 39.99rem)` to `@media (width<=39.99rem)`, which is
 *     the modern range form and the same query. Asserting on the source string
 *     therefore checks the input, not the output -- and the output is what a
 *     browser sees.
 *
 * The source is read too, for the declarations that survive minification
 * unchanged, and both are checked so neither can drift alone.
 */
function mediaBody(css: string, query: string): string {
  const start = css.indexOf(query)
  assert.notEqual(start, -1, `the stylesheet has no ${query}`)
  const open = css.indexOf('{', start)
  let depth = 0
  for (let i = open; i < css.length; i++) {
    if (css[i] === '{') depth++
    if (css[i] === '}') {
      depth--
      if (depth === 0) return stripComments(css.slice(open + 1, i))
    }
  }
  return ''
}

/** CSS comments, removed.
 *
 * The `thead` rule carries a comment that explains *why* it does not use
 * `display: none`, and it names `display: none` while doing so. An assertion
 * that greps the block for `display: none` therefore found the explanation and
 * reported the rule as doing the thing it is written to avoid.
 */
function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, '')
}


/** The built stylesheet: what a browser actually receives. */
const builtCss = (() => {
  const dir = new URL('../dist/assets/', import.meta.url)
  const file = readdirSync(dir).find((name) => name.endsWith('.css'))
  return file ? readFileSync(new URL(file, dir), 'utf8') : ''
})()

const NARROWEST = NARROWEST_VIEWPORT
const SM = 640

describe('the column widths add up', () => {
  it('the four widths total 100%', () => {
    // A table-layout:fixed table with widths summing to more than 100% lets the
    // browser scale them, and the split stops being the one that was declared.
    const total = CHUNK_COLUMN_LIST.reduce((sum, column) => sum + Number.parseFloat(column.width), 0)
    assert.equal(total, 100, `the widths total ${total}%`)
  })

  it('there are four columns, and they are the four the table renders', () => {
    assert.equal(CHUNK_COLUMN_LIST.length, 4)
    // The lookup is by key, not by index: `CHUNK_COLUMNS.id`, not
    // `CHUNK_COLUMNS[0]`. The first version matched the index form and counted
    // zero cells against a table rendering four.
    //
    // The pattern matches the whole expression including `.label` / `.width`.
    // Stopping at `CHUNK_COLUMNS.<key>` matched nothing, because in the real
    // JSX the closing brace comes after `.label`, not after the key.
    const cells = (table.match(/<td data-label=\{CHUNK_COLUMNS\.\w+\.label\}/g) ?? []).length
    assert.equal(cells, 4, `the Row renders ${cells} labelled cells`)
    const heads = (table.match(/<th scope="col">\{CHUNK_COLUMNS\.\w+\.label\}<\/th>/g) ?? []).length
    assert.equal(heads, 4, `the header renders ${heads} cells from the declaration`)
  })

  it('every column has a label, because a reflowed cell has no header above it', () => {
    for (const column of CHUNK_COLUMN_LIST) {
      assert.ok(column.label.trim().length > 0, `${column.key} has no label`)
    }
  })

  it('the two text columns get more room than the two short ones', () => {
    // A chunk id and a status badge are short. The text is the point of the
    // table, and at an even split each text column would get what the badge
    // needs and no more.
    //
    // Read by key rather than through an `Object.fromEntries(...map(...))`: the
    // declaration is a record, so the key is the access, and building a second
    // index out of it was only there because it used to be an array.
    assert.ok(
      Number.parseFloat(CHUNK_COLUMNS.source.width) > Number.parseFloat(CHUNK_COLUMNS.status.width),
      'the source column is no wider than the status column',
    )
    assert.ok(
      Number.parseFloat(CHUNK_COLUMNS.target.width) > Number.parseFloat(CHUNK_COLUMNS.id.width),
      'the target column is no wider than the id column',
    )
  })
})

describe('the even split, which is what was wrong', () => {
  it('an even split of the narrow width is too narrow for the widest header', () => {
    // The number the fix is measured against. It is in this test rather than in
    // a comment so that a change to the gutter or the type scale shows up as a
    // failure here instead of as a screenshot nobody looks at.
    const even = evenSplit(NARROWEST)
    // `reduce` with no seed throws on an empty array, and it threw here with a
    // message about the array rather than about the width, so the seed is
    // explicit.
    const widest = CHUNK_COLUMN_LIST.reduce(
      (longest, column) => (column.label.length > longest.length ? column.label : longest),
      '',
    )
    // 12 characters at 12px is about 74px, plus 16px of cell padding: 90px. The
    // even split is 90px. So the header fits *exactly*, with nothing to spare,
    // which is the actual failure: a header that fits to the pixel still wraps
    // the moment a glyph is wider than the average, and Persian has plenty of
    // those -- the `ٔ` in `ترجمهٔ` and the `ی` both run wide.
    const needed = widest.length * PX_PER_CHARACTER_AT_12PX + 16
    assert.equal(even, 90, `an even split is ${even}px, not the 90px this test describes`)
    assert.equal(widest, 'ترجمهٔ نهایی', `the widest label is "${widest}", not the one this describes`)
    assert.ok(
      needed >= even,
      `an even split gives ${even}px and the widest header needs about ${Math.round(needed)}px, ` +
        'so this test no longer describes the problem it was written for',
    )
  })

  it('the declared widths give the text columns room for a phrase', () => {
    // Below `sm` the table reflows, so a width is only claimed above the reflow
    // point -- which is the point of the reflow being that no width is enough
    // below it. The claim is therefore about the *narrowest non-reflowed*
    // screen, 640px, not about a desktop: a width that only works at 1200px
    // would be a desktop layout that happens to reflow on a phone, which is the
    // thing the monitor was not.
    assert.ok(SM > NARROWEST, 'the reflow point is not above the narrowest phone')
    const text = CHUNK_COLUMNS.target
    const share = Number.parseFloat(text?.width ?? '0') / 100
    // The `.page` gutter at this width is still 24px a side: the narrow step
    // applies below 640px, and 640 is the boundary the query is exclusive of.
    const available = SM - 48
    const atReflowPoint = Math.floor(available * share)
    // A Persian sentence at 14px needs several lines even in 200px; what the
    // column has to hold is a line or two, which this checks.
    assert.ok(
      atReflowPoint >= 180,
      `the target column is ${atReflowPoint}px at ${SM}px, too narrow to hold a line of Persian`,
    )
  })
})

describe('the reflow below sm', () => {
  const SOURCE_QUERY = '@media (max-width: 39.99rem)'
  const BUILT_QUERY = '@media (width<=39.99rem)'

  it('the reflow block reaches the built stylesheet', () => {
    // The source and the build are both checked, and the build is what a
    // browser reads. The first version of this suite asserted the source
    // string, which the minifier rewrites -- so the test was checking the
    // input and would have passed while the output was wrong.
    const body = mediaBody(builtCss, BUILT_QUERY)
    assert.ok(body.includes('.vtable'), 'the built reflow block has no .vtable rule')
    assert.ok(
      mediaBody(css, SOURCE_QUERY).includes('.vtable'),
      'the source reflow block has no .vtable rule',
    )
  })

  it('the built stylesheet is the one under test, and it exists', () => {
    // A guard on the test itself: if the build were missing, `builtCss` would
    // be empty and every assertion below would pass against nothing.
    assert.ok(builtCss.length > 1000, `the built stylesheet is ${builtCss.length} bytes`)
  })

  it('the header is hidden without leaving the accessibility tree', () => {
    // `display: none` on a `th` removes it from the tree, and the header cell
    // is the accessible name for that column. The clip technique keeps the
    // content present and the box out of the layout.
    const body = mediaBody(builtCss, BUILT_QUERY)
    assert.ok(/\.vtable thead\s*\{[\s\S]*?position:\s*absolute/.test(body), 'the thead is not clipped away')
    assert.ok(!/display:\s*none/.test(body), 'the narrow rule uses display:none, which drops the header from the tree')
  })

  it('the cells become blocks and the rows stop being table rows', () => {
    const body = mediaBody(builtCss, BUILT_QUERY)
    assert.ok(/\.vtable td\s*\{[\s\S]*?display:\s*block/.test(body), 'the cells do not stack')
    assert.ok(/\.vtable tr\s*\{[\s\S]*?display:\s*block/.test(body), 'the rows do not stack')
  })

  it('the row height is released, because a stacked row is not 96px', () => {
    // The virtualiser assumes 96px a row. That is the desktop truth, and it is
    // the reason this reflow has to release it: a block row is as tall as its
    // content, and a fixed height would clip it.
    const body = mediaBody(builtCss, BUILT_QUERY)
    assert.ok(/\.vtable td\s*\{[\s\S]*?height:\s*auto/.test(body), 'the narrow rule leaves the cell height fixed')
  })

  it('each cell prints its own label through data-label', () => {
    const body = mediaBody(builtCss, BUILT_QUERY)
    assert.ok(
      /content:\s*attr\(data-label\)/.test(body),
      'the narrow rule does not print the data-label, so a stacked value has no name',
    )
  })
})

describe('the virtualiser and the stylesheet still agree', () => {
  it('the row height in tokens.css is ROW_H', () => {
    // The comment in tokens.css says these must match. They did, and they must
    // keep matching: a mismatch does not throw, it renders blank space at the
    // bottom of the table.
    const height = /\.vtable td\s*\{[^}]*height:\s*(\d+)px/.exec(css)
    assert.ok(height, '.vtable td has no height in tokens.css')
    assert.equal(Number(height[1]), ROW_H, `CSS says ${height[1]}px, ROW_H says ${ROW_H}px`)
  })

  it('the window calculation is unchanged by any of this', () => {
    // A guard on the test itself: `computeWindow` takes a list and a scroll
    // offset, not the object shape the first version of this test assumed, so
    // the assertions would have been made against nothing.
    const rows = Array.from({ length: 100 }, (_, index) => index)
    const window = computeWindow(rows, 0, 560, ROW_H, OVERSCAN)
    assert.ok(window.start <= window.end, 'the window is inverted')
    assert.ok(window.end <= rows.length, 'the window runs past the end of the list')
    // A viewport of 560 at 96px a row is about six rows, plus the overscan.
    assert.ok(
      window.end - window.start <= Math.ceil(560 / ROW_H) + 2 * OVERSCAN,
      `the window is ${window.end - window.start} rows, more than the viewport and overscan allow`,
    )
  })
})
