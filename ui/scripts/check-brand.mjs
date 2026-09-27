/**
 * Guard the brand SVGs.
 *
 * These files are parsed as XML by the browser, by the Python `kalima_mark()`
 * helper, and by the test that checks the rendered page. Two things silently
 * break all three, and neither shows up as a visible error:
 *
 *   - `--` inside an XML comment. Legal-looking, and it makes the file fail to
 *     parse, so the mark disappears with nothing in any log.
 *   - a leftover `<!-` from an over-eager regex, which truncates the document
 *     and has the same effect.
 *
 * `npm run build` runs this first so a broken mark fails the build rather than
 * shipping a blank space where the logo should be.
 */
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const publicDir = join(here, '..', 'public')

/** Minimal well-formedness check: comments balanced, no `--` inside them, one root. */
function inspect(name, text) {
  const problems = []

  // Strip comments, then look for `--` in what is left. A `--` outside a
  // comment is harmless here; inside one it is not.
  const comments = text.match(/<!--[\s\S]*?-->/g) ?? []
  for (const comment of comments) {
    const body = comment.slice(4, -3)
    if (body.includes('--')) problems.push('a comment contains "--", which is illegal in XML')
  }
  const outside = text.replace(/<!--[\s\S]*?-->/g, '')
  if (outside.includes('<!-')) problems.push('a truncated comment marker "<!-" is present')
  if (outside.includes('-->')) problems.push('a stray "-->" is present')

  if (!text.trimStart().startsWith('<?xml')) problems.push('no XML declaration')
  if (!text.includes('<svg')) problems.push('no <svg> element')

  // Exactly one root element.
  const roots = (outside.match(/<svg[\s>]/g) ?? []).length
  if (roots !== 1) problems.push(`expected 1 <svg> root, found ${roots}`)

  return problems
}

const files = [
  join(publicDir, 'favicon.svg'),
  join(publicDir, 'brand', 'kalima-mark-light.svg'),
  join(publicDir, 'brand', 'kalima-mark-dark.svg'),
]

let broken = 0
for (const path of files) {
  const name = path.split(/[\\/]/).pop()
  let text
  try {
    text = readFileSync(path, 'utf8')
  } catch {
    console.error(`  MISSING  ${name}`)
    broken++
    continue
  }
  const problems = inspect(name, text)
  if (problems.length === 0) {
    console.log(`  ok  ${name}  (${(text.length / 1024).toFixed(1)} KB)`)
  } else {
    broken++
    console.error(`  BROKEN  ${name}`)
    for (const problem of problems) console.error(`            ${problem}`)
  }
}

// A stray file in public/ is almost always a mistake: everything Vite copies
// from there is published, so an unused draft of the mark would ship too.
const brandDir = join(publicDir, 'brand')
try {
  const present = readdirSync(brandDir).filter((name) => name.endsWith('.svg'))
  const expected = new Set(['kalima-mark-light.svg', 'kalima-mark-dark.svg'])
  const extra = present.filter((name) => !expected.has(name))
  if (extra.length > 0) {
    console.error(`  WARNING  unexpected file(s) in public/brand: ${extra.join(', ')}`)
  }
} catch {
  // The per-file check above already reported the missing directory.
}

if (broken > 0) {
  console.error('')
  console.error('  The KALIMA mark is broken. It will render as an empty space,')
  console.error('  and nothing in any log will say why.')
  console.error('')
  process.exit(1)
}
