/**
 * Refuse to build without the generated font files.
 *
 * `main.tsx` imports `./styles/fonts.generated.css`, which is produced by
 * `../docs/build_fonts.py` from the Python project and is gitignored. A fresh
 * clone therefore has no font, and without this guard the build fails with an
 * opaque module-not-found error in a file nobody is looking at. Worse, if
 * someone removed the import to make the error go away, the app would silently
 * fall back to a system font and Persian text would render in the wrong
 * typeface with nothing in the console.
 *
 * So: check the files exist, and if they do not, print the one command that
 * creates them.
 */
import { existsSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const ui = join(here, '..')

const GENERATED = join(ui, 'src', 'styles', 'fonts.generated.css')
const FONT_DIR = join(ui, 'public', 'fonts')
const EXPECTED_FILES = [
  'Vazirmatn-Regular.woff2',
  'Vazirmatn-Medium.woff2',
  'Vazirmatn-SemiBold.woff2',
  'Vazirmatn-Bold.woff2',
  'Vazirmatn-Black.woff2',
]

const problems = []

if (!existsSync(GENERATED)) {
  problems.push(`missing ${GENERATED}`)
}

if (!existsSync(FONT_DIR)) {
  problems.push(`missing ${FONT_DIR}`)
} else {
  const present = new Set(readdirSync(FONT_DIR))
  for (const filename of EXPECTED_FILES) {
    if (!present.has(filename)) problems.push(`missing ${join(FONT_DIR, filename)}`)
  }
  // A partial set would render some weights synthesised, which looks like a
  // font bug rather than a missing file.
  const extra = [...present].filter(
    (name) => name.endsWith('.woff2') && !EXPECTED_FILES.includes(name),
  )
  if (extra.length > 0) {
    console.warn(`  note: ${extra.length} unexpected woff2 file(s) in public/fonts`)
  }
}

if (problems.length > 0) {
  console.error('')
  console.error('  The local Vazirmatn font has not been generated.')
  console.error('')
  for (const problem of problems) console.error(`    - ${problem}`)
  console.error('')
  console.error('  Run this once, and again after changing a font weight in the')
  console.error('  Python project:')
  console.error('')
  console.error('    python ..\\docs\\build_fonts.py')
  console.error('')
  console.error('  It reads the woff2 files from')
  console.error('  D:\\J_BookTranslate_V\\app\\library so the font is never tracked')
  console.error('  in two repositories at once.')
  console.error('')
  process.exit(1)
}

console.log('  fonts: generated CSS and 5 weights present')
