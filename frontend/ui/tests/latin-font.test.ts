/**
 * The English UI dresses in Manrope, not in Vazirmatn's Latin.
 *
 * Asserted from the source, the way `monitor-width.test.ts` asserts the CSS
 * it depends on: the woff2 must be served locally (no CDN -- the app renders
 * offline), the face must cover the weights the UI uses, and the override
 * must be scoped to `html[lang='en']` with Vazirmatn kept second in the
 * stack, so Persian inside English sentences still finds its glyphs.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { existsSync, readFileSync, statSync } from 'node:fs'

const font = new URL('../public/fonts/Manrope-Variable.woff2', import.meta.url)
const face = readFileSync(new URL('../src/styles/fonts-latin.css', import.meta.url), 'utf8')
const tokens = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8')

describe('latin font', () => {
  it('is served from this origin, not a CDN', () => {
    assert.ok(existsSync(font), 'Manrope-Variable.woff2 is missing from public/fonts')
    assert.ok(statSync(font).size > 10000, 'the woff2 looks truncated')
  })

  it('covers every weight with one variable face', () => {
    assert.ok(/font-family:\s*'Manrope'/.test(face))
    assert.ok(/font-weight:\s*200 800/.test(face), 'weights outside 200-800 would synthesize')
    assert.ok(/\/fonts\/Manrope-Variable\.woff2/.test(face))
  })

  it('applies to English only, with Vazirmatn kept for Persian fallback', () => {
    assert.ok(/html\[lang='en'\]\s*body\s*\{[^}]*font-family:\s*'Manrope',\s*'Vazirmatn'/.test(tokens))
  })
})
