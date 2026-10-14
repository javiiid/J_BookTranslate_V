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
  directionFor,
  isDirection,
  lastLocationOf,
  locationKey,
  overallPercent,
  pairedBlocks,
  readKey,
  storedChapter,
  syncTop,
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

describe('columns pairing', () => {
  const block = (id: string, translation_html: string) => ({
    id,
    position: 0,
    original: 'x',
    translation: 'y',
    original_html: 'x',
    translation_html,
  })

  it('drops blocks with no translation, which would pair a side with a gap', () => {
    const pairs = pairedBlocks([block('a', '<p>y</p>'), block('b', ''), block('c', '<p>z</p>')])
    assert.deepEqual(pairs.map((entry) => entry.id), ['a', 'c'])
  })

  it('keeps every block when all are translated', () => {
    assert.equal(pairedBlocks([block('a', 'y')]).length, 1)
    assert.deepEqual(pairedBlocks([]), [])
  })
})

describe('synced scroll math', () => {
  it('moves the other column proportionally', () => {
    assert.equal(syncTop(50, 100, 200), 100)
    assert.equal(syncTop(0, 100, 200), 0)
    assert.equal(syncTop(100, 100, 200), 200)
  })

  it('clamps overscroll instead of flinging the view', () => {
    assert.equal(syncTop(150, 100, 200), 200)
    assert.equal(syncTop(-20, 100, 200), 0)
  })

  it('holds still rather than dividing by an unmeasured column', () => {
    assert.equal(syncTop(50, 0, 200), 0)
    assert.equal(syncTop(50, 100, 0), 0)
    assert.equal(syncTop(Number.NaN, 100, 200), 0)
  })
})

describe('per-side direction', () => {
  it('lets an explicit setting win', () => {
    assert.equal(directionFor('سلام دنیا', 'ltr'), 'ltr')
    assert.equal(directionFor('hello world', 'rtl'), 'rtl')
  })

  it('detects Arabic script as RTL, like the Python reader', () => {
    assert.equal(directionFor('<p>سلام دنیا</p>', 'auto'), 'rtl')
    assert.equal(directionFor('<p>hello world</p>', 'auto'), 'ltr')
  })

  it('falls through to detection on an unknown setting', () => {
    assert.equal(directionFor('hello', 'sideways'), 'ltr')
    assert.equal(directionFor('سلام', 'sideways'), 'rtl')
  })

  it('reads Latin-only markup as LTR', () => {
    // Tags are Latin, so markup alone must not flip a side to RTL.
    assert.equal(directionFor('<div class="x"><br></div>', 'auto'), 'ltr')
  })
})

describe('overall progress', () => {
  it('adds the chapter fraction to the chapters before it', () => {
    assert.equal(overallPercent(2, 0.5, 10), 25)
    assert.equal(overallPercent(0, 0, 4), 0)
    assert.equal(overallPercent(3, 1, 4), 100)
  })

  it('clamps instead of running past either end', () => {
    // `frac` is a 0..1 fraction: 9 clamps to a full chapter (10%), and a
    // chapter past the last one clamps to the whole book (100%).
    assert.equal(overallPercent(0, 9, 10), 10)
    assert.equal(overallPercent(0, -0.5, 10), 0)
    assert.equal(overallPercent(11, 0, 10), 100)
  })

  it('is zero rather than NaN when there is nothing to divide by', () => {
    assert.equal(overallPercent(0, 0.5, 0), 0)
    assert.equal(overallPercent(Number.NaN, 0.5, 10), 0)
  })
})

describe('remembered location', () => {
  it('shares the Python reader storage keys', () => {
    assert.equal(locationKey('job-1'), 'jbook:loc:job-1')
    assert.equal(readKey('job-1'), 'jbook:read:job-1')
  })

  it('reads the {job_id, chapter} shape both readers write', () => {
    assert.deepEqual(lastLocationOf({ job_id: 'a', chapter: 3 }), { chapter: 3 })
    assert.equal(lastLocationOf(null), null)
    assert.equal(lastLocationOf('chapter 3'), null)
    assert.equal(lastLocationOf({ chapter: -1 }), null)
    assert.equal(lastLocationOf({ chapter: Number.NaN }), null)
    assert.equal(lastLocationOf({}), null)
  })

  it('opens the explicit choice, then local memory, then server memory', () => {
    const ids = [0, 1, 2]
    assert.equal(storedChapter(ids, 2, { chapter: 1 }, { chapter: 0 }), 2)
    assert.equal(storedChapter(ids, null, { chapter: 1 }, { chapter: 0 }), 1)
    assert.equal(storedChapter(ids, null, { chapter: 9 }, { chapter: 0 }), 0)
    assert.equal(storedChapter(ids, null, null, null), null)
  })

  it('ignores a remembered chapter that no longer exists', () => {
    assert.equal(storedChapter([0, 1], null, { chapter: 7 }, { chapter: 7 }), null)
  })
})
