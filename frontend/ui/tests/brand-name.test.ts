/**
 * The product's name, spelled one way.
 *
 * ## Why a test at all
 *
 * The name is Persian: **کالیما** — k, alef, lam, yeh, mim, alef. A neighbouring
 * letter, `وا` (waw then alef), is one keystroke away and reads plausibly in a
 * heading nobody re-reads. It shipped: the dashboard greeted a reader with
 * "کالیوا خوش آمدید" while the source, the built bundle and the readme all
 * said something else, and every reviewer passed it because a typo in a product
 * name looks like a font.
 *
 * ## Why it is not an encoding check
 *
 * `tests/encoding.test.ts` already walks `src/` for mojibake, and it did not
 * catch this. Mojibake is invalid *bytes*; this is perfectly valid UTF-8
 * containing the wrong letters — valid to every tool in the chain, including
 * `git diff` and the contrast audit. Only a check on the actual letters of the
 * word finds it.
 *
 * The rule is anchored on the four-letter core, so a suffix stays allowed
 * ("کالیما UI", "کالیما — رابط جدید") while the last two letters changing — the
 * failure that happened — fails.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync, readdirSync, statSync } from 'node:fs'

const srcDir = new URL('../src/', import.meta.url)
const indexUrl = new URL('../index.html', import.meta.url)

function walk(dir: URL, rel = '', out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const child = new URL(`${entry}/`, dir)
    if (statSync(child).isDirectory()) walk(child, `${rel}${entry}/`, out)
    else if (/\.(tsx|ts|css|html)$/.test(entry)) out.push(`${rel}${entry}`)
  }
  return out
}

const files = [...walk(srcDir), '../index.html']

/** کالیما */
const NAME = 'کالیما'
/** The four-letter core a suffix may follow. */
const ROOT = 'کالیم'

/**
 * Distinct words that merely open with the same three letters.
 *
 * `کالیبراسیون` (calibration) is the product's own term for the
 * calibration workshop -- the UI says «کارگاه کالیبراسیون» in the
 * landing and workspace strings. It is not a misspelling of the name,
 * so an exact full-word match is skipped. Anything else opening with
 * کالی still fails: the allowlist is one whole word, not a prefix.
 */
const KNOWN_WORDS = new Set(['کالیبراسیون'])

describe('the product name', () => {
  it('is spelled کالیما wherever it appears', () => {
    const offenders: string[] = []
    for (const name of files) {
      const source = readFileSync(name === '../index.html' ? indexUrl : new URL(name, srcDir), 'utf8')
      // Any run of Persian letters that opens with the product's first three
      // letters but is not the name is a misspelling, whatever follows it.
      for (const match of source.matchAll(/کا[‌ ]?ل[‌ ]?ی[‌ ]?[\u0600-\u06ff]*/g)) {
        if (!match[0].startsWith(NAME) && !KNOWN_WORDS.has(match[0])) {
          offenders.push(`${name}: ${match[0]}`)
        }
      }
    }
    assert.deepEqual(
      offenders,
      [],
      'the product name is کالیما. These spell it differently:\n  ' + offenders.join('\n  '),
    )
  })

  it('actually appears, so the rule above cannot pass on an empty tree', () => {
    // A misspelling check over files that never say the name is a check that
    // passes forever. This one fails if the name disappears.
    const sources = files.map((name) =>
      readFileSync(name === '../index.html' ? indexUrl : new URL(name, srcDir), 'utf8'),
    )
    assert.ok(
      sources.some((source) => source.includes(NAME)),
      `no file under src/ mentions ${NAME}, so the check above is not looking at anything`,
    )
  })

  it('keeps the core recognisable: the name is ROOT + alef', () => {
    // The shape, so a refactor cannot "fix" the check by deleting the name.
    assert.equal(NAME.slice(0, ROOT.length), ROOT)
    assert.equal(NAME.length, ROOT.length + 1)
  })
})
