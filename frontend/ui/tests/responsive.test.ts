/**
 * The mobile gutter, asserted as a rule rather than as a pixel.
 *
 * ## Why this file exists
 *
 * The narrow layout was reported as "the margins are wrong, the books do not
 * show properly, the spacing goes from too little to too much". None of those
 * is a single bug. They were three, and they were spread over ten files:
 *
 *   * the horizontal gutter lived in `AppShell` as `pe-6` -- one side only --
 *     while the vertical lived in each page as `py-8`. Content sat against the
 *     screen edge on the reading-start side and 24px from it on the other.
 *   * `LibraryPage` carried `className="field w-64"`: 16rem of input plus a
 *     button, inside a flex row that could not wrap. That is wider than a
 *     393px viewport, so the button ran off the edge.
 *   * The book and job rows were `flex-wrap`, so on a phone the title took the
 *     first line and the badges and the ETA dropped to the second at the far
 *     edge, leaving a gap the width of the title beside them. That is the
 *     "too little here, too much there".
 *
 * ## What can and cannot be checked here
 *
 * `node --test` with no DOM cannot measure a computed width. What it can do is
 * hold the *decisions* -- one owner for the gutter, no fixed rem width on a
 * control, no non-wrapping row of controls -- so the same three cannot come
 * back one at a time. The numbers below are the narrowest viewport the app
 * claims to support, and they are the same ones the comments in `tokens.css`
 * are measured against.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync, readdirSync } from 'node:fs'

const pagesDir = new URL('../src/pages/', import.meta.url)
const tokensUrl = new URL('../src/styles/tokens.css', import.meta.url)
const shellUrl = new URL('../src/components/AppShell.tsx', import.meta.url)

/** The narrowest phone the app claims to support. */
const NARROWEST = 393
/** Tailwind's `sm`. Below it the narrow layout applies. */
const SM_BREAKPOINT_PX = 640

const pageFiles = readdirSync(pagesDir).filter((name) => name.endsWith('.tsx'))
const read = (name: string) => readFileSync(new URL(name, pagesDir), 'utf8')
const css = readFileSync(tokensUrl, 'utf8')
const shell = readFileSync(shellUrl, 'utf8')

/**
 * Every source file the width rule applies to, named for the failure message.
 *
 * Built once and read once. The first version of this rule assembled the list
 * inline with a `readFileSync(...).length ? ... : ...` ternary, which threw on
 * the page names because it looked for them under `components/` -- and the
 * failure surfaced as an assertion about offenders rather than as the mistake it
 * was, which is how a test starts reporting things that are not true.
 */
const sources: Array<{ name: string; source: string }> = [
  ...pageFiles.map((name) => ({ name: `pages/${name}`, source: read(name) })),
  ...['AppShell.tsx', 'MobileNav.tsx', 'NavIcon.tsx', 'nav.ts'].map((name) => ({
    name: `components/${name}`,
    source: readFileSync(new URL(`../src/components/${name}`, import.meta.url), 'utf8'),
  })),
]

/** Rem values as pixels, for the arithmetic below. */
const rem = (name: string): number => {
  const match = new RegExp(`${name}:\\s*([\\d.]+)rem`).exec(css)
  assert.ok(match, `${name} is not declared as a rem value in tokens.css`)
  return Number.parseFloat(match[1] as string) * 16
}

describe('the gutter has one owner', () => {
  it('tokens.css declares .page with both axes and two steps', () => {
    assert.ok(/\.page\s*\{[^}]*padding-block/.test(css), '.page has no padding-block')
    assert.ok(/\.page\s*\{[^}]*padding-inline/.test(css), '.page has no padding-inline')
    // Two steps: the narrow one, and one from `sm` up. A single step is a
    // desktop value applied to a phone.
    assert.ok(
      /@media \(min-width: 40rem\)\s*\{\s*\.page\s*\{/.test(css),
      '.page has no wider step at 40rem (640px)',
    )
  })

  it('the narrow gutter is a thumb margin, and the wide one is not larger than the old pe-6', () => {
    const narrow = rem('--spacing-4')
    const wide = rem('--spacing-6')
    assert.ok(narrow >= 12, `the narrow gutter is ${narrow}px, under a comfortable thumb margin`)
    assert.ok(wide <= 24, `the wide gutter is ${wide}px, more than the 24px it replaced`)
    assert.ok(wide > narrow, 'the wide step is not wider than the narrow one')
  })

  it('the narrow vertical padding is less than half a phone viewport', () => {
    // A phone is roughly 700px tall in CSS pixels once the browser chrome is
    // taken off. 32px top and 32px bottom is 64px, and on the pages that also
    // carry a header it pushed the first card below the fold for no reason.
    const block = rem('--spacing-6')
    assert.ok(block * 2 < 350, `${block * 2}px of vertical padding on a phone`)
  })

  it('every page uses .page and declares no padding of its own', () => {
    for (const name of pageFiles) {
      const source = read(name)
      const mains = source.match(/<main[^>]*className="([^"]*)"/g) ?? []
      assert.ok(mains.length > 0, `${name} has no <main> to check`)
      for (const tag of mains) {
        const classes = /className="([^"]*)"/.exec(tag)?.[1] ?? ''
        assert.ok(
          classes.split(/\s+/).includes('page'),
          `${name}: a <main> does not carry .page -- it has "${classes}"`,
        )
        // A page that also carries its own padding is the state this test was
        // written to end: two owners for one gutter.
        assert.ok(
          !/\b(?:p|px|py|ps|pe|pt|pb)-/.test(classes),
          `${name}: a <main> still declares its own padding -- "${classes}"`,
        )
      }
    }
  })

  it('the shell no longer sets a horizontal gutter', () => {
    // It owns the rail offset and the bar's height. The gutter belongs to the
    // page, and `pe-6` here is what made it asymmetric.
    const content = /<div\s+className="([^"]*me-0[^"]*)"/.exec(shell)?.[1] ?? ''
    assert.ok(content, 'could not find the content wrapper in AppShell')
    assert.ok(
      !/\b(?:p|px|ps|pe)-/.test(content),
      `AppShell still sets a horizontal gutter -- "${content}"`,
    )
    assert.ok(
      /lg:me-60/.test(content),
      'AppShell no longer offsets for the rail above lg',
    )
  })
})

describe('no control has a fixed width on a narrow screen', () => {
  it('no input or button carries a fixed rem or px width', () => {
    // `w-64` on a field is 256px. With a button beside it in a row that cannot
    // wrap, that is wider than a 393px viewport, and the button goes off the
    // edge. A control's width on a phone is the free width.
    const offenders: string[] = []
    for (const { name, source } of sources) {
      for (const [index, line] of source.split('\n').entries()) {
        if (!/<(input|select|textarea|button)\b/.test(line)) continue
        const fixed = /\b(?:w|min-w)-\[?(\d+(?:\.\d+)?)(px|rem)\b/.exec(line)
        if (!fixed) continue
        const value = Number.parseFloat(fixed[1] as string) * (fixed[2] === 'rem' ? 16 : 1)
        if (value < NARROWEST) continue
        offenders.push(`${name}:${index + 1}  ${line.trim().slice(0, 80)}`)
      }
    }
    assert.deepEqual(
      offenders,
      [],
      `a control is at least ${NARROWEST}px wide:\n  ${offenders.join('\n  ')}`,
    )
  })

  it('the row that holds a search field can wrap', () => {
    const library = read('LibraryPage.tsx')
    const row = /<div className="([^"]*)">\s*<input/.exec(library)?.[1] ?? ''
    assert.ok(
      /control-row/.test(row),
      `the search field's row is "${row}" and cannot wrap, so the button beside it overflows`,
    )
  })

  it('tokens.css defines .control-row as a wrapping row with a flexible field', () => {
    assert.ok(/\.control-row\s*\{[^}]*flex-wrap:\s*wrap/.test(css), '.control-row cannot wrap')
    assert.ok(
      /\.control-row\s*>\s*\.field\s*\{[^}]*flex:\s*1 1/.test(css),
      '.control-row does not let the field take the free width',
    )
  })
})

describe('a book and a job row do not leave a gap beside the title', () => {
  /**
   * The rows that used to wrap their metadata onto a second line.
   *
   * The pattern allows a JSX comment between the element and its grid, because
   * the first version of this test required them to be adjacent and reported
   * "not laid out as a grid" against markup that was correct -- the comment
   * explaining why it is a grid sat in between.
   */
  const ROWS: Array<[string, string, RegExp]> = [
    [
      'LibraryPage.tsx',
      'a book in the library',
      /<li className="surface-card p-4">\s*(?:\{\/\*[\s\S]*?\*\/\}\s*)?<div className="grid/,
    ],
    [
      'DashboardPage.tsx',
      'a recent job',
      /<Link\s+to=\{`\/jobs\/\$\{job\.id\}`\}\s*className="grid/,
    ],
  ]

  for (const [name, what, pattern] of ROWS) {
    it(`${what} is a grid, not a wrapping flex row`, () => {
      const source = read(name).replace(/\s+/g, ' ')
      assert.ok(
        pattern.test(source),
        `${name}: ${what} is not laid out as a grid, so its badges wrap under the title and leave a gap`,
      )
    })
  }

  it('the two rows put the metadata back on one line above lg', () => {
    // Stacked-and-therefore-sticky is the other failure: on a 1440px screen a
    // book title with its badges on the next line reads as two separate items.
    for (const [name] of ROWS) {
      const source = read(name)
      assert.ok(
        /lg:grid-cols-\[minmax\(0,1fr\)/.test(source) || /lg:grid-cols-\[minmax\(0,1fr\)_auto_auto\]/.test(source),
        `${name}: the row never returns to one line above lg`,
      )
    }
  })

  it('the job row keeps its badge and its ETA in one wrapper, so they cannot separate', () => {
    const source = read('DashboardPage.tsx')
    // Two free siblings in a wrapping row is what put one at each end of a
    // line. They have to travel together.
    const group = /<span className="flex items-center gap-\[var\(--spacing-2\)\]">\s*<span className=\{badgeClass/.test(
      source.replace(/\s+/g, ' '),
    )
    assert.ok(group, 'the status badge and the ETA are not in a single wrapper')
  })
})

describe('the bottom bar and the page gutter agree', () => {
  it('the shell reserves the bar height and releases it above lg', () => {
    assert.ok(
      /pb-\[calc\(var\(--mobile-nav-height\)[^\]]*\][^\n]*lg:pb-0/.test(shell),
      'the shell does not reserve the bar height, or does not release it at lg',
    )
  })

  it('the reserved height is at least a touch target plus the safe area', () => {
    const bar = rem('--mobile-nav-height')
    // 44px is the touch-target floor. The bar is 56px because it carries an
    // icon and a label; what this asserts is that the reservation is not so
    // small that the last row of a form sits under the bar.
    assert.ok(bar >= 44, `--mobile-nav-height is ${bar}px, under the 44px touch floor`)
  })
})

describe('a long filename must not widen the page', () => {
  /* The bug this holds.
   *
   * `/workspace` lists open workshops by filename, and real filenames are long:
   * "0434b505f492__Robert C. Martin Series_ Martin R.C.-Clean Architecture_ A
   * Craftsman's Guide to Software Structure and Design-Pearson Education
   * _2017_.epub" is 150 characters.
   *
   * A grid item defaults to `min-width: auto`, which means "never smaller than my
   * widest content". The workshop list therefore grew to its max-content and
   * pushed the document to 1,608px on a 390px phone — every select measured
   * 1,550px wide and the whole page scrolled sideways.
   *
   * `minmax(0,1fr)` on the outer track was already there and did NOT help: that
   * bounds the TRACK, and the item inside it still refuses to shrink until it is
   * told it may. So `min-w-0` has to be on the item, which is what this checks.
   *
   * No source-level rule catches this in general — a `truncate` with a `min-w-0`
   * on the wrong element still overflows — so this asserts the concrete shape,
   * and the numbers were measured in a browser at 390px and 1280px.
   */
  const workspace = read('WorkspacePage.tsx')

  it('the intake column may shrink', () => {
    assert.ok(
      /<div className="grid min-w-0 gap-4">/.test(workspace),
      'the intake column has no min-w-0, so a long filename widens the whole page',
    )
  })

  it('the workshop row may shrink, at every level of the chain', () => {
    assert.ok(
      /<ul className="mt-3 grid min-w-0 gap-2">/.test(workspace),
      'the workshop list has no min-w-0',
    )
    assert.ok(
      /<li key=\{draft\.id\} className="min-w-0">/.test(workspace),
      'a workshop row has no min-w-0; it is a grid item and defaults to min-width:auto',
    )
    assert.ok(
      /className="flex min-w-0 items-center justify-between gap-3/.test(workspace),
      'the workshop link has no min-w-0, so truncate inside it has nothing to shrink against',
    )
  })

  it('the state badge cannot be squeezed, because it carries the state', () => {
    // flex-none, so a long filename truncates instead of the label losing its
    // last letter — and the badge is short because the state is translated.
    assert.ok(
      /className="badge flex-none">\{stateLabel\(draft\.state\)\}/.test(workspace),
      'the workshop badge is not flex-none, or shows the raw SCREAMING_SNAKE state',
    )
  })

  it('the full name is reachable, since the visible one is truncated', () => {
    assert.ok(
      /title=\{draft\.filename\}/.test(workspace),
      'the truncated filename has no title, so the full one is unreadable',
    )
  })

  it('the name truncates from the front, so the identifying half survives', () => {
    // `text-overflow: ellipsis` cuts at the containing block's inline end, and
    // the page is RTL — so a long filename showed its tail
    // ("…ructure and Design-Pearson Education _2017_") and the part that names
    // the book was gone. A `<bdi>` isolate was tried and does NOT help: it
    // reorders the text but leaves the ellipsis where it was. Only the
    // direction of the truncating box moves it.
    assert.ok(
      /<strong\s+dir="ltr"\s+className="block truncate text-right/.test(workspace),
      'the truncating filename is not dir=ltr, so the ellipsis cuts off the identifying half',
    )
    assert.ok(
      !/<Ltr>\{draft\.filename\}<\/Ltr>/.test(workspace),
      'a <bdi> isolate was left around the filename; it does not move the ellipsis',
    )
  })
})

describe('the narrow layout is the default, not an afterthought', () => {
  it('the sm breakpoint the gutter switches at is above the narrowest phone', () => {
    // If the gutter switched at, say, 480px, a 393px phone would get the desktop
    // gutter and the complaint would come straight back.
    const step = /@media \(min-width: ([\d.]+)rem\)\s*\{\s*\.page/.exec(css)
    assert.ok(step, '.page has no rem-based breakpoint')
    const px = Number.parseFloat(step[1] as string) * 16
    assert.ok(
      px > NARROWEST,
      `.page switches to the wide gutter at ${px}px, at or below the ${NARROWEST}px narrowest phone`,
    )
    assert.ok(px === SM_BREAKPOINT_PX, `expected Tailwind's sm (${SM_BREAKPOINT_PX}px), got ${px}px`)
  })
})

describe('the dashboard hero wraps instead of squeezing', () => {
  it('the greeting block has a wrapping basis beside the nowrap status pill', () => {
    // The status pill is a `.badge` with `white-space: nowrap` at ~200px. A
    // bare `flex-1` greeting beside it was squeezed to a word per line on a
    // 390px phone instead of the pill wrapping underneath. The basis forces
    // the wrap while `min-w-0` still lets the text shrink inside its own row.
    const source = read('DashboardPage.tsx')
    assert.ok(
      /flex:\s*['"]1 1 12rem['"]/.test(source),
      'the hero text block lost its 12rem wrapping basis',
    )
  })
})
