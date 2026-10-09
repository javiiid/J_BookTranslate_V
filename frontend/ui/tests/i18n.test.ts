/**
 * The bilingual contract, asserted without a DOM.
 *
 * Two rules keep the English UI from rotting while Persian moves on:
 *
 *   1. Every key in `fa.ts` exists in `en.ts` (and nothing extra hides
 *      there) -- a missing English string would otherwise render as a key
 *      or a blank, discovered by a user rather than a build.
 *   2. The pure helpers (`format.ts`, `dashboard.ts`) answer in the active
 *      language: Persian by default, English after the toggle. The default
 *      is asserted because every existing test and caller was written
 *      against Persian output.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { en } from '../src/i18n/en.ts'
import { fa } from '../src/i18n/fa.ts'
import { setLocale } from '../src/lib/locale.ts'
import { LANGUAGE_KEY } from '../src/i18n/lang.ts'
import { fa as num, faAgo, faDuration, statusLabel } from '../src/lib/format.ts'
import { greeting, heroStatus } from '../src/lib/dashboard.ts'

describe('dictionary parity', () => {
  it('every Persian key has an English mirror and nothing extra', () => {
    const faKeys = Object.keys(fa).sort()
    const enKeys = Object.keys(en).sort()
    assert.deepEqual(enKeys, faKeys)
  })

  it('no English string is empty or a copy-paste of the key', () => {
    for (const [key, value] of Object.entries(en)) {
      assert.ok(value.trim(), `${key} has an empty English string`)
      assert.notEqual(value, key, `${key} was never translated`)
    }
  })

  it('interpolations survive translation', () => {
    // A {var} the code fills must exist on both sides, or the English
    // sentence prints a raw placeholder.
    const token = (s: string) => new Set((s.match(/\{[^}]+\}/g) ?? []).sort())
    for (const key of Object.keys(fa) as Array<keyof typeof fa>) {
      assert.deepEqual(
        token(en[key]),
        token(fa[key]),
        `${key} interpolates different variables per language`,
      )
    }
  })

  it('every nav destination has a label and a short label', () => {
    for (const route of ['dashboard', 'workspace', 'convert', 'jobs', 'library', 'reader', 'account']) {
      assert.ok(fa[`nav.${route}` as keyof typeof fa].trim())
      assert.ok(en[`nav.${route}` as keyof typeof en].trim())
    }
  })
})

describe('shared storage key', () => {
  it('the React UI reads the same key as the Python switcher', () => {
    // `app/core/web_i18n.py` reads 'jbook-language'. A second key here
    // would split the preference: English on one UI, Persian on the other.
    assert.equal(LANGUAGE_KEY, 'jbook-language')
  })
})

describe('locale-aware formatters', () => {
  it('default to Persian digits', () => {
    setLocale('fa')
    assert.equal(num(1234567), '۱٬۲۳۴٬۵۶۷')
    assert.equal(statusLabel('running'), 'در حال ترجمه')
    assert.equal(greeting(9), 'صبح بخیر')
  })

  it('answer in English after the toggle', () => {
    setLocale('en')
    try {
      assert.equal(num(1234567), '1,234,567')
      assert.equal(statusLabel('running'), 'Translating')
      assert.equal(statusLabel('mystery'), 'mystery')
      assert.equal(greeting(9, 'en'), 'Good morning')
      assert.ok(faAgo(new Date(Date.now() - 60000).toISOString()).includes('ago'))
      assert.ok(faDuration(90).includes('min'))
      assert.ok(heroStatus({ running: 0, stuck: 0, total: 0 }, 'en').includes('No jobs'))
    } finally {
      setLocale('fa')
    }
  })
})
