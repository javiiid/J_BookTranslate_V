/**
 * The auth form's client-side guards.
 *
 * These mirror the server bounds in `app/auth/service.py` so a typo'd email
 * is caught before a round trip. They are convenience only -- the server
 * rechecks everything -- and this pins the two sides to the same rules:
 * an 8-char minimum, a 200-char ceiling, one @ with a dot, a non-blank name.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { validDisplayName, validEmail, validPassword } from '../src/lib/auth.ts'

describe('auth validators', () => {
  it('accepts a normal address and rejects the usual junk', () => {
    assert.equal(validEmail('user@example.com'), true)
    assert.equal(validEmail('  USER@Example.COM '), true)
    for (const bad of ['', 'not-an-email', 'a@b', 'a@b.', '@example.com', 'x'.repeat(170) + '@example.com']) {
      assert.equal(validEmail(bad), false, `${bad} passed`)
    }
  })

  it('holds the 8..200 password window the server enforces', () => {
    assert.equal(validPassword('s3cret-pass'), true)
    assert.equal(validPassword('short'), false)
    assert.equal(validPassword(''), false)
    assert.equal(validPassword('x'.repeat(201)), false)
    assert.equal(validPassword('x'.repeat(200)), true)
  })

  it('requires a non-blank display name inside 100 chars', () => {
    assert.equal(validDisplayName('Test User'), true)
    assert.equal(validDisplayName('   '), false)
    assert.equal(validDisplayName(''), false)
    assert.equal(validDisplayName('  padded  '), true)
    assert.equal(validDisplayName('x'.repeat(101)), false)
  })
})
