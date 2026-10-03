/**
 * WCAG contrast checker for the token file.
 *
 * A brand palette is easy to adopt and easy to make unreadable. #4C7C92 on
 * white is the brand colour, and it is fine as a button fill, but it is too
 * light for body text. Rather than eyeball that, this parses tokens.css and
 * checks every foreground/background pair the design system claims to use.
 *
 * Thresholds (WCAG 2.2):
 *   AA normal text  4.5:1
 *   AA large text   3.0:1   (>=18.66px bold or >=24px)
 *   AA non-text     3.0:1   (borders that carry meaning, focus rings)
 */
import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

const TOKENS = new URL('../src/styles/tokens.css', import.meta.url)

type RGB = [number, number, number]
type Mode = 'day' | 'dark'
/** [theme, foreground, background, minimum ratio, why] */
type Pair = [Mode, string, string, number, string]

/** #rgb, #rrggbb, #rrggbbaa. Alpha is resolved against a backdrop. */
function parse(colour: string, backdrop = '#ffffff'): RGB {
  let hex = colour.trim().replace('#', '')
  if (hex.length === 3) hex = hex.split('').map((c) => c + c).join('')
  const r = parseInt(hex.slice(0, 2), 16) / 255
  const g = parseInt(hex.slice(2, 4), 16) / 255
  const b = parseInt(hex.slice(4, 6), 16) / 255
  const alpha = hex.length === 8 ? parseInt(hex.slice(6, 8), 16) / 255 : 1
  if (alpha === 1) return [r, g, b]
  const [br, bg, bb] = parse(backdrop)
  return [r * alpha + br * (1 - alpha), g * alpha + bg * (1 - alpha), b * alpha + bb * (1 - alpha)]
}

function luminance(rgb: RGB): number {
  // noUncheckedIndexedAccess makes a bare tuple destructure `number | undefined`,
  // so the values are read by index with an explicit fallback.
  const channel = (index: number): number => {
    const value = rgb[index] ?? 0
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2)
}

export function contrast(a: string, b: string): number {
  const la = luminance(parse(a, b))
  const lb = luminance(parse(b, a))
  const [hi, lo] = la > lb ? [la, lb] : [lb, la]
  return (hi + 0.05) / (lo + 0.05)
}

/* ------------------------------------------------------------------ */
/* The pairs the design system actually renders                        */
/* ------------------------------------------------------------------ */

const AA = 4.5
const AA_LARGE = 3.0
const AA_NON_TEXT = 3.0

/**
 * [theme, foreground, background, minimum, why]
 *
 * The theme is explicit because the dark block *overrides the same names* as
 * :root. An earlier version of this test asked for `--dark-text-primary`, which
 * does not exist, and silently resolved to the day value -- so every dark pair
 * "failed" while actually comparing day colours. Resolve per theme instead.
 */
const PAIRS: Pair[] = [
  // Day mode
  ['day', '--color-text-primary', '--color-background', AA, 'day: body text on the page'],
  ['day', '--color-text-primary', '--color-surface', AA, 'day: body text on a card'],
  ['day', '--color-text-primary', '--color-surface-elevated', AA, 'day: body text on an elevated panel'],
  ['day', '--color-text-primary', '--color-surface-sunken', AA, 'day: body text on a sunken panel'],
  ['day', '--color-text-secondary', '--color-background', AA, 'day: secondary text'],
  ['day', '--color-text-secondary', '--color-surface', AA, 'day: secondary text on a card'],
  ['day', '--color-text-secondary', '--color-surface-elevated', AA, 'day: secondary on an elevated panel'],
  ['day', '--color-text-muted', '--color-surface', AA, 'day: muted caption text'],
  ['day', '--color-text-muted', '--color-background', AA, 'day: muted text on the page'],
  ['day', '--color-text-muted', '--color-surface-elevated', AA, 'day: muted on an elevated panel'],
  ['day', '--color-text-inverse', '--color-primary', AA, 'day: label on a primary button'],
  ['day', '--color-text-inverse', '--color-primary-hover', AA, 'day: primary button, hover'],
  ['day', '--color-text-inverse', '--color-primary-active', AA, 'day: primary button, active'],
  ['day', '--color-primary', '--color-background', AA_LARGE, 'day: brand large text only'],
  ['day', '--color-primary', '--color-surface', AA_LARGE, 'day: brand large text on a card'],
  ['day', '--color-accent-strong', '--color-background', AA, 'day: cream emphasis text'],
  ['day', '--color-accent-strong', '--color-surface', AA, 'day: cream emphasis on a card'],
  ['day', '--color-accent-strong', '--color-accent-subtle', AA, 'day: cream emphasis on the cream wash'],
  ['day', '--color-link', '--color-background', AA, 'day: link text'],
  ['day', '--color-link', '--color-surface', AA, 'day: link on a card'],
  ['day', '--color-text-brand', '--color-surface', AA, 'day: brand text on a card'],
  ['day', '--color-text-brand', '--color-primary-subtle', AA, 'day: brand text on the subtle wash'],
  ['day', '--color-success', '--color-surface', AA, 'day: success text'],
  ['day', '--color-success', '--color-success-subtle', AA, 'day: success text on its own wash'],
  ['day', '--color-warning', '--color-surface', AA, 'day: warning text'],
  ['day', '--color-warning', '--color-warning-subtle', AA, 'day: warning text on its own wash'],
  ['day', '--color-error', '--color-surface', AA, 'day: error text'],
  ['day', '--color-error', '--color-error-subtle', AA, 'day: error text on its own wash'],
  ['day', '--color-info', '--color-surface', AA, 'day: info text'],
  ['day', '--color-info', '--color-info-subtle', AA, 'day: info text on its own wash'],
  ['day', '--color-text-inverse', '--color-error', AA, 'day: label on a solid danger button'],
  ['day', '--color-text-inverse', '--color-success', AA, 'day: label on a solid success button'],

  // Dark mode
  ['dark', '--color-text-primary', '--color-background', AA, 'dark: body text'],
  ['dark', '--color-text-primary', '--color-surface', AA, 'dark: body text on a card'],
  ['dark', '--color-text-primary', '--color-surface-elevated', AA, 'dark: body text on an elevated panel'],
  ['dark', '--color-text-primary', '--color-surface-sunken', AA, 'dark: body text on a sunken panel'],
  ['dark', '--color-text-secondary', '--color-background', AA, 'dark: secondary text'],
  ['dark', '--color-text-secondary', '--color-surface', AA, 'dark: secondary on a card'],
  ['dark', '--color-text-secondary', '--color-surface-elevated', AA, 'dark: secondary on an elevated panel'],
  ['dark', '--color-text-muted', '--color-surface', AA, 'dark: muted caption text'],
  ['dark', '--color-text-muted', '--color-background', AA, 'dark: muted on the page'],
  ['dark', '--color-text-muted', '--color-surface-elevated', AA, 'dark: muted on an elevated panel'],
  ['dark', '--color-text-muted', '--color-surface-sunken', AA, 'dark: muted on a sunken panel'],
  ['dark', '--color-text-inverse', '--color-primary', AA, 'dark: label on an aqua primary button'],
  ['dark', '--color-text-inverse', '--color-primary-hover', AA, 'dark: aqua button, hover'],
  ['dark', '--color-text-inverse', '--color-accent', AA, 'dark: label on an aqua action'],
  ['dark', '--color-accent', '--color-background', AA, 'dark: aqua text on the page'],
  ['dark', '--color-accent', '--color-surface', AA, 'dark: aqua text on a card'],
  ['dark', '--color-accent', '--color-surface-elevated', AA, 'dark: aqua text on an elevated panel'],
  ['dark', '--color-accent', '--color-surface-sunken', AA, 'dark: aqua text on a sunken panel'],
  // Every status colour is checked against the elevated surface too, not just
  // the card. The elevated tier is a different lightness, so a colour that
  // passes on one can fail on the other, and the failure only shows up on the
  // components that sit on a panel.
  ['dark', '--color-warning', '--color-surface-elevated', AA, 'dark: warning on an elevated panel'],
  ['dark', '--color-error', '--color-surface-elevated', AA, 'dark: error on an elevated panel'],
  ['dark', '--color-info', '--color-surface-elevated', AA, 'dark: info on an elevated panel'],
  ['dark', '--color-link', '--color-surface-elevated', AA, 'dark: link on an elevated panel'],
  ['day', '--color-success', '--color-surface-elevated', AA, 'day: success on an elevated panel'],
  ['day', '--color-warning', '--color-surface-elevated', AA, 'day: warning on an elevated panel'],
  ['day', '--color-error', '--color-surface-elevated', AA, 'day: error on an elevated panel'],
  ['day', '--color-link', '--color-surface-elevated', AA, 'day: link on an elevated panel'],
  ['dark', '--color-accent-strong', '--color-background', AA, 'dark: cream emphasis on the page'],
  ['dark', '--color-accent-strong', '--color-surface', AA, 'dark: cream emphasis on a card'],
  ['dark', '--color-accent-strong', '--color-surface-elevated', AA, 'dark: cream emphasis elevated'],
  ['dark', '--color-link', '--color-background', AA, 'dark: link on the page'],
  ['dark', '--color-link', '--color-surface', AA, 'dark: link on a card'],
  ['dark', '--color-text-brand', '--color-surface', AA, 'dark: brand text on a card'],
  ['dark', '--color-text-brand', '--color-surface-elevated', AA, 'dark: brand text elevated'],
  ['dark', '--color-success', '--color-surface', AA, 'dark: success text'],
  // The elevated surface is lighter than the card, so a status colour that
  // passes on a card can still fail on top of it. This pair measured 4.36:1 and
  // was missed until the rendered pages were checked rather than the tokens in
  // isolation.
  ['dark', '--color-success', '--color-surface-elevated', AA, 'dark: success on an elevated panel'],
  ['dark', '--color-success', '--color-success-subtle', AA, 'dark: success on its own wash'],
  ['dark', '--color-warning', '--color-surface', AA, 'dark: warning text'],
  ['dark', '--color-warning', '--color-warning-subtle', AA, 'dark: warning on its own wash'],
  ['dark', '--color-error', '--color-surface', AA, 'dark: error text'],
  ['dark', '--color-error', '--color-error-subtle', AA, 'dark: error on its own wash'],
  ['dark', '--color-info', '--color-surface', AA, 'dark: info text'],
  ['dark', '--color-info', '--color-info-subtle', AA, 'dark: info on its own wash'],
  ['dark', '--color-text-inverse', '--color-error', AA, 'dark: label on a solid danger button'],
  ['dark', '--color-text-inverse', '--color-success', AA, 'dark: label on a solid success button'],

  // Non-text: borders that carry meaning, focus rings, progress fill
  ['day', '--color-border-strong', '--color-surface', AA_NON_TEXT, 'day: strong border on a card'],
  ['day', '--color-border-strong', '--color-background', AA_NON_TEXT, 'day: strong border on the page'],
  ['day', '--color-focus', '--color-background', AA_NON_TEXT, 'day: focus ring'],
  ['day', '--color-focus', '--color-surface', AA_NON_TEXT, 'day: focus ring on a card'],
  ['day', '--color-focus', '--color-surface-elevated', AA_NON_TEXT, 'day: focus ring on a panel'],
  ['day', '--color-progress-fill', '--color-progress-track', AA_NON_TEXT, 'day: progress fill against its track'],
  ['day', '--color-primary', '--color-surface', AA_NON_TEXT, 'day: button fill on a card'],
  ['dark', '--color-border-strong', '--color-surface', AA_NON_TEXT, 'dark: strong border on a card'],
  // The elevated surface is the case a single border token cannot serve: the
  // surface is #1F506B, lighter than a blue border would be, so a lighter
  // border measures 2.3:1 and vanishes. It needs its own, darker token.
  ['dark', '--color-border-strong-elevated', '--color-surface-elevated', AA_NON_TEXT,
    'dark: border on an elevated panel'],
  ['day', '--color-border-strong-elevated', '--color-surface-elevated', AA_NON_TEXT,
    'day: border on an elevated panel'],
  ['dark', '--color-focus', '--color-background', AA_NON_TEXT, 'dark: focus ring'],
  ['dark', '--color-focus', '--color-surface', AA_NON_TEXT, 'dark: focus ring on a card'],
  ['dark', '--color-accent', '--color-background', AA_NON_TEXT, 'dark: focus ring on the page'],
  ['dark', '--color-accent', '--color-surface', AA_NON_TEXT, 'dark: accent on a card'],
  ['dark', '--color-progress-fill', '--color-progress-track', AA_NON_TEXT, 'dark: progress fill against its track'],
  ['dark', '--color-accent', '--color-surface-elevated', AA_NON_TEXT, 'dark: accent on a panel'],

  // The mobile bottom bar. The indicator fill and the ink inside it are one pair
  // and not two, because the fill is meaningless without the ink: what a reader
  // actually sees is the icon on the circle, so only the ratio between those two
  // says whether the selected item is legible. Checked against the bar's own
  // surface rather than the page, because that is what it is drawn on.
  ['day', '--color-nav-indicator-ink', '--color-nav-indicator', AA, 'day: the selected bar icon on its fill'],
  ['dark', '--color-nav-indicator-ink', '--color-nav-indicator', AA, 'dark: the selected bar icon on its fill'],
  // And the unselected label, which is the other thing on the bar.
  ['day', '--color-text-muted', '--color-surface', AA, 'day: an unselected bar label on the bar'],
  // The primary action's resting wash: a muted icon on `--color-primary-subtle`,
  // which is what the bar actually draws for the one item that is neither
  // selected nor plain.
  ['day', '--color-text-muted', '--color-primary-subtle', AA, 'day: the resting primary icon on its wash'],
  ['dark', '--color-text-muted', '--color-primary-subtle', AA, 'dark: the resting primary icon on its wash'],
  // NOT `--color-text-muted` on `--color-nav-indicator`: that pair is 1.30:1 in
  // the dark theme, because the selection fill is the aqua there. It is left out
  // on purpose and the constraint is recorded, because it is the mistake the
  // indicator invites -- using one fill for both "selected" and "at rest" -- and
  // it is invisible until the dark theme is rendered. The bar keeps two
  // distinguishable unselected fills for exactly this reason.
  // The rule under the selected label carries the selection without relying on
  // the fill being distinguishable, so it is held to the non-text threshold.
  ['day', '--color-accent-strong', '--color-surface', AA_NON_TEXT, 'day: the selection rule on the bar'],
  ['dark', '--color-accent-strong', '--color-surface', AA_NON_TEXT, 'dark: the selection rule on the bar'],
]

/**
 * Pull `--name: value;` out of a selector block.
 *
 * The selector is matched together with its `{` on purpose. An earlier version
 * used `indexOf('.dark')` and hit the text inside
 * `@custom-variant dark (&:where(.dark, .dark *));` instead of the real block,
 * so every dark token came back "missing" while the day values were being
 * compared against themselves.
 */
function readBlock(css: string, selector: string): Record<string, string> {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = new RegExp(`${escaped}\\s*\\{`).exec(css)
  if (!match) return {}
  const open = match.index + match[0].length - 1
  const close = css.indexOf('}', open)
  const body = css.slice(open + 1, close)
  const tokens: Record<string, string> = {}
  for (const entry of body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    // Groups are `string | undefined` under noUncheckedIndexedAccess, and a
    // group that is undefined would silently poison a lookup.
    const name = entry[1]
    const value = entry[2]
    if (name !== undefined && value !== undefined) tokens[name] = value.trim()
  }
  return tokens
}

const css = readFileSync(TOKENS, 'utf8')
const root = readBlock(css, ':root')
const theme = readBlock(css, '@theme')
const dark = readBlock(css, '.dark')

/** Day values, including anything only declared in @theme. */
const day = { ...theme, ...root }
/** Dark values, falling back to @theme for anything not overridden. */
const darkResolved = { ...theme, ...dark }

function resolve(name: string, mode: 'day' | 'dark'): string {
  const table: Record<string, string> = mode === 'dark' ? darkResolved : day
  const value = table[name]
  if (value === undefined) {
    throw new Error(
      `token ${name} is not defined for ${mode}. ` +
        `day: ${day[name] ?? 'missing'}, dark: ${darkResolved[name] ?? 'missing'}`,
    )
  }
  return value
}

describe('tokens.css contrast', () => {
  for (const [mode, fg, bg, minimum, why] of PAIRS) {
    it(`${why} (${fg} on ${bg})`, () => {
      const ratio = contrast(resolve(fg, mode), resolve(bg, mode))
      assert.ok(
        ratio >= minimum,
        `${mode}: ${fg} (${resolve(fg, mode)}) on ${bg} (${resolve(bg, mode)}) ` +
          `is ${ratio.toFixed(2)}:1, needs ${minimum}:1`,
      )
    })
  }
})

describe('every token is defined in both themes', () => {
  // A token present in :root but missing from .dark silently falls back to the
  // day colour, which is how a dark surface ends up with dark text on it.
  const shared = Object.keys(root).filter((name) => name.startsWith('--color-'))
  for (const name of shared) {
    it(`${name} is overridden in .dark`, () => {
      assert.ok(name in dark, `${name} has no dark value; it would keep its day colour`)
    })
  }
})

describe('palette provenance', () => {
  it('uses the exact brand hexes it claims to', () => {
    // These four are given, not derived. A near-miss means someone re-derived
    // a brand colour instead of copying it.
    const given = {
      cream: '#F1E6B6',
      aqua: '#B0E1E4',
      blue: '#4C7C92',
      white: '#FFFFFF',
      darkBg: '#071426',
      darkSurface: '#1F506B',
    }
    const all = JSON.stringify([day, dark])
    for (const [name, hex] of Object.entries(given)) {
      assert.ok(all.toLowerCase().includes(hex.toLowerCase()), `${name} ${hex} is missing`)
    }
  })
})

/**
 * The type scale has a hard floor.
 *
 * The caption step was 0.6875rem, which is 11px, and it was reported as "the
 * text is not readable". Latin at 11px is merely small. Persian is different
 * because the script joins: the letters need their shapes to be told apart, and
 * at 11px with a tight line height the descenders of one line meet the
 * ascenders of the next.
 *
 * So 12px is a floor, asserted here rather than left to taste. A scale is
 * exactly the kind of thing that drifts down one step at a time.
 */
describe('type scale', () => {
  const scale = Object.entries(theme).filter(([name]) => name.startsWith('--text-'))
  const MINIMUM_PX = 12

  it('declares the steps the components use', () => {
    const names = scale.map(([name]) => name)
    for (const required of ['--text-h1', '--text-h2', '--text-h3', '--text-body', '--text-small', '--text-caption', '--text-label', '--text-button']) {
      assert.ok(names.includes(required), `${required} is missing from the scale`)
    }
  })

  for (const [name, value] of scale) {
    if (name.includes('--line-height')) continue
    it(`${name} is at least ${MINIMUM_PX}px`, () => {
      const rem = /^([\d.]+)rem$/.exec(value.trim())
      assert.ok(rem, `${name} is "${value}", expected a rem value`)
      const px = Number.parseFloat(rem[1] as string) * 16
      assert.ok(
        px >= MINIMUM_PX,
        `${name} is ${px}px, below the ${MINIMUM_PX}px floor for Persian text`,
      )
    })
  }

  it('keeps the sizes distinct apart from the one documented exception', () => {
    // Adjacent identical sizes defeat the purpose of a scale: nothing tells the
    // reader which is meant to be the quieter one. `--text-button` shares a size
    // with `--text-label` on purpose, because a button label and a field label
    // are the same kind of thing, and that pairing is the only allowed repeat.
    const ALLOWED_PAIR = '--text-button'
    const sizes = scale
      .filter(([name]) => !name.includes('--line-height') && name !== ALLOWED_PAIR)
      .map(([, value]) => Number.parseFloat(/([\d.]+)rem/.exec(value)?.[1] ?? '0') * 16)
      .sort((a, b) => a - b)
    for (let i = 1; i < sizes.length; i++) {
      assert.notEqual(sizes[i], sizes[i - 1], `two steps share ${sizes[i]}px`)
    }
  })

  it('gives running text a line height generous enough for joined script', () => {
    // Headings are exempt: they are short, and a tight leading is what makes a
    // large size look deliberate. Body copy is where Persian ascenders and
    // descenders actually collide, so that is what is asserted.
    const RUNNING = new Set(['--text-body', '--text-small', '--text-caption', '--text-label', '--text-button'])
    for (const [name, value] of scale) {
      if (!name.includes('--line-height')) continue
      const step = name.replace('--line-height', '')
      if (!RUNNING.has(step)) continue
      const ratio = Number.parseFloat(value)
      assert.ok(
        ratio >= 1.6,
        `${step} has a line height of ${ratio}, too tight for Persian ascenders and descenders`,
      )
    }
  })
})
