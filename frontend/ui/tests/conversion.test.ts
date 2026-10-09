import assert from 'node:assert/strict'
import { describe, it, mock } from 'node:test'
import {
  CONVERSION_MAX_BYTES, conversionFileError, conversionFormatDescription, conversionFormatLabel, conversionForm, convertFile, parseConversionResult,
} from '../src/lib/conversion.ts'
import { setLocale } from '../src/lib/locale.ts'

const response = {
  id: 'abc123',
  versions: [{ name: 'docx', filename: 'sample.docx', download: '/downloads/convert/abc123/docx' }],
}

describe('conversion validation', () => {
  it('accepts supported input extensions without rejecting dotted filenames', () => {
    for (const name of ['کتاب.نسخه.PDF', 'book.epub', 'captions.srt', 'notes.txt', 'readme.md']) {
      assert.equal(conversionFileError({ name, size: 20 }), null)
    }
  })

  it('rejects unsupported, empty and oversized files', () => {
    assert.ok(conversionFileError({ name: 'book.docx', size: 20 }))
    assert.ok(conversionFileError({ name: 'empty.txt', size: 0 }))
    assert.ok(conversionFileError({ name: 'large.pdf', size: CONVERSION_MAX_BYTES + 1 }))
    assert.equal(conversionFileError({ name: 'edge.pdf', size: CONVERSION_MAX_BYTES }), null)
  })

  it('uses the existing multipart field names and deduplicates formats', () => {
    const file = new File(['متن آزمایشی'], 'test.txt')
    const form = conversionForm(file, ['docx', 'markdown', 'docx'])
    assert.equal((form.get('convert_book') as File).name, 'test.txt')
    assert.deepEqual(form.getAll('convert_outputs'), ['docx', 'markdown'])
    assert.throws(() => conversionForm(file, []), /حداقل/)
  })
})

describe('conversion results', () => {
  it('accepts the backend contract, including partial results', () => {
    assert.deepEqual(parseConversionResult(response), response)
  })

  it('rejects empty output instead of showing success', () => {
    assert.throws(() => parseConversionResult({ id: 'abc123', versions: [] }), /هیچ خروجی/)
  })

  it('rejects invalid results and unexpected download destinations', () => {
    for (const value of [null, {}, { id: '../other', versions: [] }]) {
      assert.throws(() => parseConversionResult(value))
    }
    for (const download of ['javascript:alert(1)', 'https://example.com/file', '/downloads/convert/other/docx']) {
      assert.throws(() => parseConversionResult({ ...response, versions: [{ ...response.versions[0], download }] }))
    }
  })
})

describe('conversion locale', () => {
  it('labels and errors answer in English after the toggle', () => {
    setLocale('en')
    try {
      assert.equal(conversionFormatLabel('txt_bilingual'), 'Text')
      assert.ok(conversionFormatDescription('docx').includes('Word'))
      assert.ok(conversionFileError({ name: 'book.docx', size: 20 })?.includes('Unsupported'))
    } finally {
      setLocale('fa')
    }
  })

  it('defaults to Persian without any setup', () => {
    assert.equal(conversionFormatLabel('txt_bilingual'), 'متن')
  })
})

describe('conversion transport', () => {
  it('posts a real multipart request to the existing endpoint', async () => {
    const fetchMock = mock.method(globalThis, 'fetch', async (path: string, options: RequestInit) => {
      assert.equal(path, '/api/convert')
      assert.equal(options.method, 'POST')
      assert.ok(options.body instanceof FormData)
      assert.deepEqual(options.body.getAll('convert_outputs'), ['docx'])
      return Response.json(response, { status: 201 })
    })
    try {
      assert.deepEqual(await convertFile(new File(['hello'], 'test.txt'), ['docx']), response)
    } finally { fetchMock.mock.restore() }
  })

  it('surfaces backend errors', async () => {
    const fetchMock = mock.method(globalThis, 'fetch', async () => Response.json({ error: 'فضای کافی وجود ندارد' }, { status: 400 }))
    try {
      await assert.rejects(convertFile(new File(['hello'], 'test.txt'), ['docx']), /فضای کافی/)
    } finally { fetchMock.mock.restore() }
  })

  it('handles non-JSON proxy errors', async () => {
    const fetchMock = mock.method(globalThis, 'fetch', async () => new Response('Bad Gateway', { status: 502 }))
    try {
      await assert.rejects(convertFile(new File(['hello'], 'test.txt'), ['docx']), /پاسخ قابل خواندن/)
    } finally { fetchMock.mock.restore() }
  })

  it('does not retry an ambiguous network failure automatically', async () => {
    const fetchMock = mock.method(globalThis, 'fetch', async () => { throw new TypeError('Failed to fetch') })
    try {
      await assert.rejects(convertFile(new File(['hello'], 'test.txt'), ['docx']), /نتیجه عملیات مشخص نیست/)
      assert.equal(fetchMock.mock.callCount(), 1)
    } finally { fetchMock.mock.restore() }
  })
})
