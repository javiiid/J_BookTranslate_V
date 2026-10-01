/**
 * Tests for the formatting helpers, with one rule that matters more than the
 * rest: `maskSecretLike` must never print anything shaped like a credential.
 *
 * The reason it exists is specific. `/api/account/portal` returns each API key's
 * `name` verbatim from a free-text database column, and in this installation
 * that column holds a string beginning with `sk-`. Rendering the name as-is would
 * put a secret in the DOM, in the page source, and in any screenshot a user
 * takes to ask "why is this broken".
 *
 * The masking is a client-side guard on a server-side defect, so the test is
 * written adversarially: every shape of token a provider might use, and the
 * ordinary labels that must survive untouched.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

// `format.ts`, not `format.tsx`, and that is load-bearing. An intermediate version
// of this module held the `<bdi>` isolate as JSX, which forced the file to
// `.tsx` -- and then every test importing it died with
// `ERR_UNKNOWN_FILE_EXTENSION` before a single assertion ran, because
// `node --test` strips types but does not transform JSX. `Ltr` is written with
// `createElement` instead so this stays a plain module.
import { Ltr, fa, faDate, ltr, maskSecretLike, usd } from '../src/lib/format.ts'

describe('ltr', () => {
  /* The isolate that keeps a Latin run from being reordered inside Persian text.

     The first version of this returned a React element typed as
     `React.ReactNode`, and the call site interpolated it into a template string.
     That rendered the literal text:

         <p>یک ترجمهٔ ناتمام پیدا شد — [object Object] از [object Object] بخش…</p>

     The <bdi> was working perfectly, around the wrong content. So this returns a
     string, and the element is `Ltr`.
   */
  it('returns a string, never a node', () => {
    assert.equal(typeof ltr('۸۸٪'), 'string')
    assert.equal(ltr('۸۸٪'), '۸۸٪')
    // The identity is the point: the isolate is the `Ltr` component, and this
    // exists so a call site in a template string is a no-op rather than a
    // "[object Object]".
    assert.equal(ltr(usd(0.0774)), '$0.08')
  })

  it('never produces the string "[object Object]"', () => {
    for (const value of ['۱۲', '$0.08', '$0.07 – $0.09', 'gpt-5.6-luna', 'EN', '٪۵۰']) {
      assert.ok(!String(ltr(value)).includes('object'), value)
    }
  })

  it('Ltr renders a <bdi>, so the isolate reaches the DOM', () => {
    // The isolate itself is a React element, so it is checked by its shape
    // rather than by string: a component returning a bare string would leave the
    // number to the bidi algorithm, which is the whole defect.
    const element = Ltr({ children: '$0.08' })
    assert.equal(element.type, 'bdi')
    assert.deepEqual(element.props, { children: '$0.08' })
  })

  it('Ltr keeps its children as they were given', () => {
    // Numbers arrive as strings from fa(); nothing here may reformat them.
    assert.equal(Ltr({ children: fa(129013) }).props.children, fa(129013))
    assert.equal(Ltr({ children: usd(0.0774) }).props.children, '$0.08')
  })
})

describe('usd', () => {
  it('writes two decimals and a dollar sign', () => {
    assert.equal(usd(0.0774), '$0.08')
    assert.equal(usd(0), '$0.00')
    assert.equal(usd(2.5815), '$2.58')
  })

  it('keeps Latin digits, because a price is compared against an invoice', () => {
    // `fa(0.08)` is "۰٫۰۸". A currency figure in Persian text is still
    // conventionally written with a decimal point, and a reader checking it
    // against their provider's invoice is looking for "$0.08".
    assert.equal(usd(0.08), '$0.08')
    assert.notEqual(usd(0.08), fa(0.08))
  })

  it('a sub-cent amount does not print as $0.00', () => {
    /* Resuming bills only what is left, and the remainder is often a few cents.

       Four chunks of the cheapest model cost about $0.0024. At two decimals that
       is "$0.00" -- the exact string the whole `known` flag exists to keep off
       the page, because a zero beside a "start translating" button reads as free.
       A reader who has just watched the dialog separate "free" from "unknown"
       would read it as free.
     */
    assert.equal(usd(0.0024), '$0.0024')
    assert.equal(usd(0.0006), '$0.0006')
    assert.notEqual(usd(0.0024), '$0.00')
    // And a real zero is still a real zero, not four decimals of nothing.
    assert.equal(usd(0), '$0.00')
  })

  it('the boundary is a cent, not a rounding accident', () => {
    assert.equal(usd(0.01), '$0.01')
    assert.equal(usd(0.009), '$0.0090')
    assert.equal(usd(0.0099), '$0.0099')
  })

  it('a negative amount keeps its sign and gains no digits', () => {
    // Not expected from the estimator, but a formatter that silently prints
    // "$0.0000" for a negative number would hide a sign error rather than show it.
    assert.equal(usd(-0.5), '$-0.50')
    assert.equal(usd(-0.002), '$-0.0020')
  })

  it('a non-finite amount is not a price', () => {
    assert.equal(usd(Number.NaN), '—')
    assert.equal(usd(Number.POSITIVE_INFINITY), '—')
  })
})

describe('maskSecretLike', () => {
  /* Every one of these came out of a real database or a real config file. */
  const SECRETS = [
    'sk-kXVqGs4XodYyJejWfYvIIG0HJhajJ0r8ZPSI80gtLlqeiBJK',
    'sk-t2zlniCgJBQTQbDbX7q3rlVmIqmE0GtpFFoH8kHdQHHLdSKu',
    'sk-proj-abc123XYZ-_456',
    'jbt_live_GG4e9Q2restoftheprefix',
    'pk_live_51H8xYzabcdefghijklmnop',
    'api_key_0123456789abcdef0123456789abcdef',
    'ghp_16C7e42F292c6912E7710c838347Ae178B4a',
    'a'.repeat(64),
    'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0',
  ]

  for (const secret of SECRETS) {
    it(`never prints ${secret.slice(0, 6)}… in full`, () => {
      const masked = maskSecretLike(secret)
      assert.notEqual(masked, secret, 'the secret was returned unchanged')
      // The point is that the tail is gone, not that the string changed.
      assert.ok(
        !masked.includes(secret.slice(8)),
        `${masked} still contains the body of the secret`,
      )
    })
  }

  it('keeps a short prefix so two keys can be told apart', () => {
    const masked = maskSecretLike(SECRETS[0] as string)
    assert.ok(masked.startsWith('sk-k'), masked)
    assert.ok(masked.includes('•'))
  })

  it('masks a secret too short to keep a prefix from', () => {
    // Eight characters: keeping four would leave half of it visible, which is
    // not a mask.
    assert.equal(maskSecretLike('sk-1234'), '••••')
  })

  it('keeps only the public part of a short prefixed secret', () => {
    // Eleven characters. `sk-1` is the scheme, not the secret, so showing it
    // identifies nothing.
    assert.equal(maskSecretLike('sk-12345678'), 'sk-1•••••••')
  })

  /* Labels are user data, not credentials. Masking them would make the page
     useless, so the guard has to be narrow. */
  const LABELS = [
    'ترجمهٔ روز',
    'CI key',
    'laptop',
    'test',
    'personal',
    'gpt-5.6-luna',
    'هایپرلینک',
    'backup-2026',
  ]

  for (const label of LABELS) {
    it(`leaves the label ${JSON.stringify(label)} alone`, () => {
      assert.equal(maskSecretLike(label), label)
    })
  }

  it('reports nothing for an empty value', () => {
    assert.equal(maskSecretLike(''), '—')
    assert.equal(maskSecretLike('   '), '—')
    assert.equal(maskSecretLike(null), '—')
    assert.equal(maskSecretLike(undefined), '—')
  })

  it('does not mask a short dotted word', () => {
    // A version or a filename must survive.
    assert.equal(maskSecretLike('v1.2.3'), 'v1.2.3')
  })
})

describe('fa', () => {
  it('formats a number with Persian digits', () => {
    assert.equal(fa(0), '۰')
    assert.equal(fa(1234), '۱٬۲۳۴')
  })

  it('handles a negative', () => {
    assert.ok(fa(-5).includes('۵'))
  })
})

describe('faDate', () => {
  it('reports nothing for a missing value', () => {
    assert.equal(faDate(null), '—')
    assert.equal(faDate(undefined), '—')
  })

  it('reports nothing for an unparseable value', () => {
    // A "Invalid Date" reaching the screen is worse than a dash.
    assert.equal(faDate('not a date'), '—')
  })

  it('formats a real timestamp', () => {
    const out = faDate('2026-09-22T19:57:29.649953+00:00')
    assert.notEqual(out, '—')
    assert.ok(out.length > 4)
  })
})
