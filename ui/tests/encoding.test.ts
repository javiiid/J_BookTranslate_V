/**
 * No file in `src` may contain double-encoded text.
 *
 * Two pages shipped with every Persian string in them written as mojibake: the
 * browser rendered `Ù…Ø¨Ø¯Ø£` where it should have shown `متن`. It was invisible
 * in review, invisible to `tsc`, invisible to the linter, and invisible to the
 * contrast audit -- that audit reported 622 elements with zero failures, because
 * it measures colour and size, and the text measured perfectly. The glyphs were
 * simply the wrong glyphs.
 *
 * Nothing in the toolchain can catch this. A mojibake file is valid UTF-8, valid
 * TypeScript and valid JSX. Only a check for the *content* of the string finds
 * it, so that is what this is.
 *
 * The signature is reliable. Correctly encoded Persian never contains a character
 * from the Latin-1 supplement, and `â€` -- the UTF-8 bytes of U+2026 read as
 * Windows-1252 -- cannot occur in Persian source at all.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, extname, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const SRC = join(here, '..', 'src')

/* What the damage looks like, in the two forms it takes. */
const MARKERS = ['Ù', 'Ø', 'â€', 'Ã©', 'Å', 'Æ']

const EXTENSIONS = new Set(['.ts', '.tsx', '.css', '.html'])

function walk(dir: string): string[] {
  const found: string[] = []
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) {
      found.push(...walk(path))
    } else if (EXTENSIONS.has(extname(path))) {
      found.push(path)
    }
  }
  return found
}

const files = walk(SRC)
const persian = (text: string) => [...text].filter((c) => c >= '؀' && c <= 'ۿ').length

describe('encoding', () => {
  it('finds the source tree at all', () => {
    // A silently empty walk would make every assertion below pass for the wrong
    // reason, which is the failure mode this file exists to prevent.
    assert.ok(files.length > 10, `only found ${files.length} source file(s)`)
  })

  for (const file of files) {
    const relative = file.slice(SRC.length + 1)

    it(`${relative} is not double-encoded`, () => {
      const raw = readFileSync(file)
      const text = raw.toString('utf8')

      // Round-tripping through Buffer.toString replaces invalid sequences rather
      // than throwing, so check the bytes are genuinely valid UTF-8 first.
      assert.ok(
        Buffer.compare(Buffer.from(text, 'utf8'), raw) === 0,
        `${relative} is not valid UTF-8`,
      )

      const hits = MARKERS.filter((marker) => text.includes(marker))
      assert.equal(
        hits.length,
        0,
        `${relative} contains ${hits.join(' ')}, which is UTF-8 read as Windows-1252. ` +
          `Reverse it with docs/fix_mojibake.py.`,
      )
    })
  }

  it('holds real Persian text, so the check above is not passing on an empty tree', () => {
    // The reverse risk: a src tree with no Persian in it at all would sail past
    // the mojibake check while the product had lost its language. This interface
    // is Persian, so Persian has to be present.
    const total = files.reduce((sum, file) => sum + persian(readFileSync(file, 'utf8')), 0)
    assert.ok(total > 100, `only ${total} Persian characters across src/`)
  })
})
