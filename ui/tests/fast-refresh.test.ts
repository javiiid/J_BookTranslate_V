/**
 * Fast Refresh only works when a module exports components and nothing else.
 *
 * ## The complaint
 *
 * "It keeps popping up in the frontend." The Vite log named it exactly:
 *
 *     hmr invalidate /src/pages/JobDetailPage.tsx
 *     Could not Fast Refresh ("ACTION_LABELS" export is incompatible)
 *
 * Vite's React plugin cannot hot-update a module that exports a component *and*
 * a plain value: the two have different update semantics, so instead of swapping
 * the component in place it gives up and asks for a full reload. Every save then
 * threw away the page state -- a half-typed search box, the page you were on --
 * which is what "keeps popping up" felt like from the browser.
 *
 * It is not a warning that can be ignored. `npm run lint` reported nothing,
 * because oxlint's `only-export-components` rule is not in the config for these
 * paths, and a build succeeds, because the file is valid either way. Only Vite,
 * at runtime, refuses.
 *
 * ## What this test holds
 *
 * Two rules, both checkable from the source:
 *
 *   1. A module that exports a component exports no other value. Types are
 *      exempt: `export interface Props` is erased before the module ever runs,
 *      so it cannot affect refresh. A `const`, a re-export of a `const`, or a
 *      class can.
 *   2. Every re-export in a component file points at a component.
 *
 * The second rule is the one that bit. `JobDetailPage` did not declare
 * `ACTION_LABELS` as an export at all -- it re-exported it on a separate line,
 * `export { ACTION_LABELS }`, which a check for `export const` does not see.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync, readdirSync, statSync } from 'node:fs'

const srcDir = new URL('../src/', import.meta.url)

/** Every .tsx under src, recursively. */
function walk(dir: URL, rel = '', out: Array<{ name: string; source: string }> = []) {
  for (const entry of readdirSync(dir)) {
    const child = new URL(`${entry}/`, dir)
    if (statSync(child).isDirectory()) {
      walk(child, `${rel}${entry}/`, out)
    } else if (entry.endsWith('.tsx') && !entry.endsWith('.d.tsx')) {
      // Built from `entry` rather than from the URL: a URL for a *file* keeps the
      // trailing slash the directory URL carried, so every name came out as
      // `JobDetailPage.tsx/` and the "is the real file in the list" check below
      // failed on a suite that had in fact found it.
      out.push({ name: `src/${rel}${entry}`, source: readFileSync(child, 'utf8') })
    }
  }
  return out
}

const files = walk(srcDir)

/** Names this module exports as a component. */
function componentExports(source: string): Set<string> {
  const names = new Set<string>()
  for (const match of source.matchAll(/^export function (\w+)/gm)) names.add(match[1] as string)
  for (const match of source.matchAll(/^export default function (\w+)/gm)) names.add(match[1] as string)
  for (const match of source.matchAll(/^export const (\w+)\s*[:=][^=]*\(?[\w\s,{}]*\)?\s*=>\s*<?[A-Z]/gm)) {
    names.add(match[1] as string)
  }
  return names
}

/** Names this module exports as a value that is not a component. */
function valueExports(source: string): string[] {
  const found: string[] = []
  for (const match of source.matchAll(/^export (?:const|let|var|class|enum) (\w+)/gm)) {
    found.push(match[1] as string)
  }
  // `export { A, B }` -- the re-export form, which is what JobDetailPage used
  // and what a check for `export const` misses entirely. A clause with `from`
  // is a pass-through of a name this module does not own; it is still a value
  // in the module's export list, so it counts either way.
  for (const match of source.matchAll(/^export \{([^}]*)\}/gm)) {
    for (const part of (match[1] as string).split(',')) {
      const name = part.trim().split(/\s+as\s+/)[0]?.trim()
      if (name) found.push(name)
    }
  }
  return found
}

describe('no component module exports a plain value', () => {
  const offenders: string[] = []
  for (const { name, source } of files) {
    const components = componentExports(source)
    if (components.size === 0) continue
    for (const value of valueExports(source)) {
      if (components.has(value)) continue
      offenders.push(`${name}  ->  ${value}`)
    }
  }

  it('every component file exports components only', () => {
    // Vite's message: `Could not Fast Refresh ("X" export is incompatible)`.
    // Each one of these turns a hot update into a full page reload.
    assert.deepEqual(
      offenders,
      [],
      'these exports break Fast Refresh, so every save reloads the page:\n  ' +
        offenders.join('\n  '),
    )
  })

  it('the suite is looking at real files, not an empty list', () => {
    // A rule that matches nothing because the walk found nothing passes
    // forever. The count is asserted so a broken walk cannot hide a regression.
    assert.ok(files.length >= 20, `only found ${files.length} .tsx files under src`)
    assert.ok(
      files.some((f) => f.name.endsWith('JobDetailPage.tsx')),
      'JobDetailPage is not in the file list, so this suite is not checking the file that broke',
    )
  })
})

describe('the rule is aimed at the right thing', () => {
  it('does not flag a type export', () => {
    // Types are erased before the module runs, so a module may export an
    // interface next to a component without affecting refresh. Flagging those
    // would be a false positive and would push the constants out for nothing.
    const source = [
      'export interface Props {',
      '  label: string',
      '}',
      'export function Thing({ label }: Props) {',
      '  return <div>{label}</div>',
      '}',
      'export type Tone = "a" | "b"',
    ].join('\n')
    assert.deepEqual(valueExports(source), [])
  })

  it('does flag a re-export, which is the form that actually broke it', () => {
    const source = [
      'const ACTION_LABELS = { approve: "تایید" }',
      'export function Page() {',
      '  return <div>{ACTION_LABELS.approve}</div>',
      '}',
      'export { ACTION_LABELS }',
    ].join('\n')
    assert.deepEqual(componentExports(source), new Set(['Page']))
    assert.deepEqual(valueExports(source), ['ACTION_LABELS'])
  })
})
