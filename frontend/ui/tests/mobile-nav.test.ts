/**
 * The mobile bottom bar, asserted on the data rather than on rendered pixels.
 *
 * There is no DOM here -- `node --test` with static assertions, the same shape as
 * the other suites -- so these cannot measure a colour or a computed height.
 * What they can hold is the set of decisions that are easy to change by accident
 * and expensive to notice: how many items fit, what the labels say, and which
 * token carries the selection.
 *
 * The contrast of the bar is not tested here. It is in
 * `tokens.contrast.test.ts`, against the same tokens this file names, because a
 * contrast assertion that reads its colours from the component rather than from
 * `tokens.css` would pass while the component used a different pair.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync } from 'node:fs'
import { MOBILE_NAV, NAV, primaryItem } from '../src/components/nav.ts'

/** The narrowest phone the bar is built for, in CSS pixels. */
const NARROWEST = 393

/** `--text-caption` is the floor: 0.75rem, asserted as 12px in the token test. */
const LABEL_PX = 12

describe('the bar carries five destinations', () => {
  it('has five items', () => {
    // A bar is a summary. Six is where the labels start to suffer, and the step
    // below --text-caption does not exist in this project.
    assert.equal(MOBILE_NAV.length, 5)
  })

  it('every item in the bar also exists in the rail', () => {
    // A bar item that is not a rail item is a destination with no desktop
    // equivalent, which is a decision nobody has made yet.
    const routes = new Set(NAV.map((item) => item.to))
    for (const item of MOBILE_NAV) {
      assert.ok(routes.has(item.to), `${item.to} is in the bar but not in the rail`)
    }
  })

  it('has no duplicate destinations', () => {
    const seen = new Set<string>()
    for (const item of MOBILE_NAV) {
      assert.ok(!seen.has(item.to), `${item.to} appears twice in the bar`)
      seen.add(item.to)
    }
  })

  it('every bar item has a label, and so does every rail item', () => {
    for (const item of [...NAV, ...MOBILE_NAV]) {
      assert.ok(item.label.trim(), `${item.to} has no label`)
      assert.ok(item.short.trim(), `${item.to} has no short label`)
    }
  })
})

describe('the labels are one word, because the bar is narrow', () => {
  it('no short label has more than one word', () => {
    // Not a style preference. At 12px a Persian word plus a space is about
    // 48px, five of them plus the gaps is most of a 393px screen, and two words
    // do not fit. `truncate` would then cut a word in half, which is worse than
    // a different word: a truncation cannot know that "پایش ترجمه" cut to five
    // characters is not Persian.
    for (const item of MOBILE_NAV) {
      const words = item.short.trim().split(/\s+/)
      assert.equal(words.length, 1, `${item.short} is ${words.length} words`)
    }
  })

  it('no short label is long enough to overflow its column', () => {
    // Vazirmatn at 12px averages about 6.2px per Persian character, so a
    // column of NARROWEST/5 = 78.6px holds roughly 12 characters with the
    // padding. Twelve is the ceiling; the labels in use are five to eight.
    const column = NARROWEST / MOBILE_NAV.length
    const budget = Math.floor((column - 8) / 6.2)
    for (const item of MOBILE_NAV) {
      assert.ok(
        item.short.length <= budget,
        `${item.short} is ${item.short.length} characters, the column holds about ${budget}`,
      )
    }
  })

  it('the bar uses the size the type scale allows as a floor', () => {
    // Guard against a later edit swapping the label for a smaller step. The
    // floor is 12px and the scale asserts it, but only for the steps it
    // declares; this pins the bar to one of them.
    const css = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8')
    const caption = /--text-caption:\s*([\d.]+)rem/.exec(css)
    assert.ok(caption, '--text-caption is not declared')
    assert.equal(Number.parseFloat(caption[1] as string) * 16, LABEL_PX)
  })
})

describe('the theme switch is in the bar, and is not a destination', () => {
  /* Dark mode was unreachable on a phone. The only copy of the toggle lived in
   * the rail's footer, and the rail is `hidden` below `lg` — so the control was
   * in the DOM, focusable, and invisible at every width a phone actually uses.
   *
   * A floating corner button was tried and rejected: at 390px it sat on top of
   * the dashboard's status pill, and a full-width invisible strip across the top
   * of the page swallowed taps meant for the header. The bar's chrome slot is
   * the one place that is present on every page and collides with nothing.
   */

  const bar = readFileSync(new URL('../src/components/MobileNav.tsx', import.meta.url), 'utf8')

  it('the bar renders the theme toggle', () => {
    assert.ok(/<ThemeToggle \/>/.test(bar), 'the mobile bar has no theme toggle, so dark mode is unreachable on a phone')
  })

  it('the toggle is a sibling of the list, not a sixth destination', () => {
    // MOBILE_NAV is five because six puts the label under 12px at 393px, and
    // 12px is this project's floor for Persian. Adding an item there would
    // trade a real constraint for a preference; a sibling costs no label.
    const afterList = bar.slice(bar.lastIndexOf('</ul>'))
    assert.ok(
      /<ThemeToggle \/>/.test(afterList),
      'the toggle is inside the list, so it has taken a destination slot',
    )
    assert.equal(MOBILE_NAV.length, 5, 'MOBILE_NAV is no longer five destinations')
  })

  it('the toggle does not shrink', () => {
    assert.ok(
      /<div className="flex flex-none items-center ps-\[var\(--spacing-1\)\]">/.test(bar),
      'the toggle wrapper can be squeezed, so the button loses its touch target',
    )
  })

  it('the rail keeps its own copy, so a desktop does not need the bar', () => {
    const shell = readFileSync(new URL('../src/components/AppShell.tsx', import.meta.url), 'utf8')
    assert.ok(
      /<Sidebar \/>\s*<MobileNav \/>/.test(shell),
      'AppShell no longer renders exactly one Sidebar and one MobileNav',
    )
    assert.ok(/<ThemeToggle \/>/.test(shell), 'the rail footer has no theme toggle')
  })
})

describe('the primary action', () => {
  it('is marked, and exactly one item is', () => {
    // A second primary would give the bar two circles that both look chosen.
    const primaries = MOBILE_NAV.filter((item) => item.primary)
    assert.equal(primaries.length, 1, `primary marked on ${primaries.length} items`)
  })

  it('is reported by the helper the component uses', () => {
    // The component calls primaryItem(); if that disagreed with the data the
    // emphasis would land on the wrong destination with nothing to show it.
    const found = primaryItem(MOBILE_NAV)
    assert.ok(found, 'primaryItem found nothing')
    assert.ok(found.primary)
    assert.ok(MOBILE_NAV.some((item) => item.to === found.to))
  })
})

describe('the bar and the rail are declared together', () => {
  it('the component file names the shared model, not its own copy of the list', () => {
    // A second hand-written list of destinations is how a bar and a rail end up
    // offering different products. The list lives in nav.tsx and both read it.
    const bar = readFileSync(new URL('../src/components/MobileNav.tsx', import.meta.url), 'utf8')
    assert.ok(
      /from '\.\/nav'/.test(bar),
      'MobileNav does not import the shared navigation model',
    )
    assert.ok(
      /MOBILE_NAV/.test(bar),
      'MobileNav does not read MOBILE_NAV',
    )
  })

  it('the rail reads the same list', () => {
    const shell = readFileSync(new URL('../src/components/AppShell.tsx', import.meta.url), 'utf8')
    assert.ok(/from '\.\/nav'/.test(shell), 'AppShell does not import the shared model')
    assert.ok(/\bNAV\.map\(/.test(shell), 'the rail does not map over NAV')
  })
})

describe('both navigations are in the tree, one of them hidden', () => {
  it('the rail is display-none below lg and the bar is display-none above it', () => {
    // Not `visibility: hidden`, and not conditionally rendered. A
    // `visibility: hidden` landmark is still focusable and still announces
    // itself, so a keyboard user on a phone would tab into a rail they cannot
    // see. `hidden` takes it out of the accessibility tree.
    const shell = readFileSync(new URL('../src/components/AppShell.tsx', import.meta.url), 'utf8')
    const bar = readFileSync(new URL('../src/components/MobileNav.tsx', import.meta.url), 'utf8')
    assert.ok(/hidden[^\n]*lg:flex/.test(shell), 'the rail is not hidden below lg')
    assert.ok(/lg:hidden/.test(bar), 'the bar is not hidden above lg')
  })

  it('the shell reserves the bar height, and only below lg', () => {
    // A fixed bar over the last row of a form is the failure this guards. The
    // padding reads the same token the bar uses, so the two cannot drift, and
    // `lg:pb-0` gives the space back where the bar is not rendered.
    const shell = readFileSync(new URL('../src/components/AppShell.tsx', import.meta.url), 'utf8')
    assert.ok(
      /pb-\[calc\(var\(--mobile-nav-height\)[^\]]*\][^\n]*lg:pb-0/.test(shell),
      'the shell does not reserve the bar height, or does not release it at lg',
    )
  })

  it('the bar is the only thing that uses --mobile-nav-height, and the token is declared', () => {
    const css = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8')
    assert.ok(/--mobile-nav-height:\s*[\d.]+rem/.test(css), 'the height token is not declared')
    const bar = readFileSync(new URL('../src/components/MobileNav.tsx', import.meta.url), 'utf8')
    assert.ok(/var\(--mobile-nav-height\)/.test(bar), 'the bar does not read the height token')
  })
})

describe('the rail has no dead-end reader button', () => {
  it('bare /reader is not a destination', () => {
    // Bare `/reader` names no book and renders NotFound, so a rail button to
    // it was a 404 with an active state. It was removed rather than relinked:
    // books open at `/reader/:id` from the library, the dashboard and the
    // monitor, and those links are pinned in `tests/routing.test.ts`.
    const dead = NAV.filter((item) => item.to === '/reader')
    assert.deepEqual(dead, [])
  })
})
