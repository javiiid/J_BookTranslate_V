/**
 * Reading-setting decisions, asserted without a DOM.
 *
 * The bounds mirror the server validation on `PUT /api/reader/settings`
 * (`app/web.py`): the page clamps instantly, the server re-clamps
 * authoritatively. A control that offered a value the server refuses would
 * save nothing while reporting success, so these pin the exact edges.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  DIRECTION_OPTIONS,
  FONT_SIZE_FALLBACK,
  FONT_SIZE_MAX,
  FONT_SIZE_MIN,
  LINE_HEIGHT_FALLBACK,
  LINE_HEIGHT_OPTIONS,
  READER_MODES,
  WIDTH_FALLBACK,
  WIDTH_OPTIONS,
  clampFontSize,
  clampLineHeight,
  clampWidth,
  isDirection,
  toReaderMode,
} from '../src/lib/reading.ts'

describe('the reading mode', () => {
  it('accepts every mode the Python settings sheet offers', () => {
    assert.deepEqual([...READER_MODES], ['translation', 'original', 'bilingual', 'columns'])
    for (const mode of READER_MODES) {
      assert.equal(toReaderMode(mode), mode)
    }
  })

  it('falls back to bilingual on a mode the client does not know', () => {
    // An unknown mode must render something, not nothing. Bilingual is this
    // port's home view; the server default (`translation`) is honoured by
    // sending, not by rendering.
    assert.equal(toReaderMode('columns-3d'), 'bilingual')
    assert.equal(toReaderMode(undefined), 'bilingual')
    assert.equal(toReaderMode(''), 'bilingual')
  })
})

describe('font size clamping', () => {
  it('holds the server window of 14 to 30', () => {
    assert.equal(clampFontSize(13), FONT_SIZE_MIN)
    assert.equal(clampFontSize(31), FONT_SIZE_MAX)
    assert.equal(clampFontSize(18), 18)
  })

  it('truncates like the server int() instead of rounding', () => {
    assert.equal(clampFontSize(18.9), 18)
  })

  it('falls back to 18 on a non-number', () => {
    assert.equal(clampFontSize(Number.NaN), FONT_SIZE_FALLBACK)
  })
})

describe('line height clamping', () => {
  it('offers the sheet options and holds the server window', () => {
    assert.deepEqual([...LINE_HEIGHT_OPTIONS], [1.7, 1.9, 2.1])
    assert.equal(clampLineHeight(1.2), 1.4)
    assert.equal(clampLineHeight(3), 2.6)
    assert.equal(clampLineHeight(1.9), 1.9)
  })

  it('falls back to 1.9 on a non-number', () => {
    assert.equal(clampLineHeight(Number.NaN), LINE_HEIGHT_FALLBACK)
  })
})

describe('width clamping', () => {
  it('offers the sheet options and holds the server window', () => {
    assert.deepEqual([...WIDTH_OPTIONS], [640, 760, 880])
    assert.equal(clampWidth(400), 560)
    assert.equal(clampWidth(1400), 1000)
    assert.equal(clampWidth(760.7), 760)
  })

  it('falls back to 760 on a non-number', () => {
    assert.equal(clampWidth(Number.NaN), WIDTH_FALLBACK)
  })
})

describe('reading direction', () => {
  it('knows exactly the three values the endpoint accepts', () => {
    assert.deepEqual([...DIRECTION_OPTIONS], ['auto', 'rtl', 'ltr'])
    assert.ok(isDirection('auto') && isDirection('rtl') && isDirection('ltr'))
    assert.equal(isDirection(''), false)
    assert.equal(isDirection('RTL'), false)
  })
})
