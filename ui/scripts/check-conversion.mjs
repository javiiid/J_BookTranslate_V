import assert from 'node:assert/strict'

const origin = process.env.KALIMA_UI_ORIGIN ?? 'http://127.0.0.1:5173'
const form = new FormData()
form.append('convert_book', new File(['KALIMA conversion smoke test.\n\nمتن آزمایشی فارسی برای تبدیل فایل.'], 'conversion-smoke.txt'))
for (const format of ['markdown', 'docx', 'translated_pdf', 'txt_bilingual', 'json_segments']) {
  form.append('convert_outputs', format)
}
const response = await fetch(`${origin}/api/convert`, { method: 'POST', body: form })
const body = await response.json()
assert.equal(response.status, 201, JSON.stringify(body))
assert.ok(body.versions?.length, 'No conversion output generated')
for (const version of body.versions) {
  const download = await fetch(new URL(version.download, origin))
  const bytes = await download.arrayBuffer()
  assert.equal(download.status, 200, version.name)
  assert.ok(bytes.byteLength > 0, `${version.name} is empty`)
  console.log(`${version.name}: HTTP ${download.status}, ${bytes.byteLength} bytes`)
}
console.log(`${body.versions.length}/5 output formats generated and downloaded`)
