/**
 * Check the live backend against the TypeScript types this port depends on.
 *
 * A type-checked build proves nothing about the wire. This calls the real
 * endpoints and asserts the fields the components read, so a contract change
 * surfaces here rather than as an empty tab in the browser.
 *
 * Field names are not invented: each one is quoted with the Python line that
 * produces it, so a mismatch points at both sides.
 */
const BASE = process.env.JBT_API ?? 'http://127.0.0.1:8765'

let failures = 0

function check(label, ok, detail = '') {
  if (!ok) failures++
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${label}${detail ? `  (${detail})` : ''}`)
}

async function get(path) {
  const response = await fetch(`${BASE}${path}`, { headers: { Accept: 'application/json' } })
  const text = await response.text()
  let body = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = { __unparsed: text.slice(0, 120) }
  }
  return { status: response.status, body }
}

// Wait for the backend rather than failing on a cold start.
for (let attempt = 0; attempt < 30; attempt++) {
  try {
    const probe = await fetch(`${BASE}/api/health`)
    if (probe.ok) break
  } catch {
    /* not up yet */
  }
  await new Promise((resolve) => setTimeout(resolve, 500))
}

console.log('=== /api/health ===')
console.log('-'.repeat(66))
const health = await get('/api/health')
check('backend is up', health.status === 200, `status ${health.status}`)
check('has status and message', typeof health.body?.status === 'string' && typeof health.body?.message === 'string')

console.log()
console.log('=== /api/jobs — the Job shape JobDetailPage reads ===')
console.log('-'.repeat(66))
const jobs = await get('/api/jobs')
check('responds', jobs.status === 200, `status ${jobs.status}`)
const items = Array.isArray(jobs.body?.items) ? jobs.body.items : []
check('has items', items.length > 0, `${items.length} job(s)`)

if (items.length === 0) {
  console.log()
  console.log('  no jobs in the database; the per-job checks below are skipped')
  console.log(`  (run a translation first, or point JBT_API at a populated instance)`)
  console.log()
  console.log('FAILURES:', failures)
  process.exit(failures ? 1 : 0)
}

const job = items[0]
// Fields read by OverviewTab / the header / the action buttons.
const JOB_FIELDS = [
  'id', 'filename', 'filetype', 'file_size', 'source_language', 'target_language',
  'model', 'mode', 'status', 'style', 'created_at', 'updated_at', 'started_at',
  'error', 'can_stop', 'can_resume', 'can_cancel',
  'progress', 'health', 'eta_seconds', 'chunks_per_minute',
  'assets', 'qa_report', 'quality', 'output_path',
]
for (const field of JOB_FIELDS) {
  check(`job.${field} is present`, field in job, job[field] === undefined ? 'undefined' : typeof job[field])
}
check('job.progress is an object with percent', typeof job.progress?.percent === 'number',
  `percent=${job.progress?.percent}`)
check('job.status is a known value',
  ['queued', 'running', 'stopping', 'paused', 'stopped', 'completed', 'failed', 'cancelled'].includes(job.status),
  job.status)

console.log()
console.log('=== /api/jobs/{id} ===')
console.log('-'.repeat(66))
const one = await get(`/api/jobs/${encodeURIComponent(job.id)}`)
check('responds', one.status === 200, `status ${one.status}`)
check('the single job matches the list entry', one.body?.id === job.id)
check('asset_downloads is present (AssetsTab links)',
  one.body?.asset_downloads === undefined || typeof one.body.asset_downloads === 'object',
  one.body?.asset_downloads === undefined ? 'undefined' : `${Object.keys(one.body.asset_downloads).length} entry(ies)`)
check('assets is an object', one.body?.assets && typeof one.body.assets === 'object')
if (one.body?.asset_downloads) {
  const bad = Object.entries(one.body.asset_downloads)
    .filter(([, href]) => typeof href !== 'string' || !href.startsWith('/'))
  check('every asset_downloads value is a path the browser can fetch', bad.length === 0,
    bad.length ? JSON.stringify(bad.slice(0, 2)) : `${Object.keys(one.body.asset_downloads).length} links`)
}

console.log()
console.log('=== /api/jobs/{id}/chunks — the windowed table ===')
console.log('-'.repeat(66))
const chunks = await get(`/api/jobs/${encodeURIComponent(job.id)}/chunks`)
check('responds', chunks.status === 200, `status ${chunks.status}`)
check('has available flag', typeof chunks.body?.available === 'boolean', String(chunks.body?.available))
check('has translated count', typeof chunks.body?.translated === 'number', String(chunks.body?.translated))
const chunkItems = Array.isArray(chunks.body?.items) ? chunks.body.items : []
check('items is a list', Array.isArray(chunks.body?.items), `${chunkItems.length} chunk(s)`)
if (chunkItems.length > 0) {
  const first = chunkItems[0]
  for (const field of ['id', 'chapter', 'source', 'target', 'flagged']) {
    check(`chunk.${field} is present`, field in first, first[field] === undefined ? 'undefined' : typeof first[field])
  }
  check('chunk.id is a string (the API stringifies the dict key)', typeof first.id === 'string', String(first.id).slice(0, 24))
  check('chunk.target is a string, empty when untranslated', typeof first.target === 'string',
    first.target === '' ? '(empty)' : `${String(first.target).length} chars`)
  check('chunk.flagged is a boolean', typeof first.flagged === 'boolean')
  check('the API sends no `notes` field, so the UI must derive it',
    !('notes' in first), Object.keys(first).join(','))
  // The flag markers the UI's regex looks for must be the ones the server uses.
  const NOTE = /\{(NOTE|BOUNDARY_WARNING|WARNING)[:\s][^}]*\}/
  const withMarker = chunkItems.filter((c) => NOTE.test(String(c.target || '')) || NOTE.test(String(c.source || '')))
  const serverAgreed = withMarker.every((c) => c.flagged === true)
  check('every chunk carrying a NOTE/WARNING marker is flagged by the server', serverAgreed,
    `${withMarker.length} chunk(s) carry a marker`)
}

console.log()
console.log('=== /api/jobs/{id}/logs — the Logs tab ===')
console.log('-'.repeat(66))
const logs = await get(`/api/jobs/${encodeURIComponent(job.id)}/logs`)
check('responds', logs.status === 200, `status ${logs.status}`)
check('has items list', Array.isArray(logs.body?.items), `${logs.body?.items?.length ?? 'none'} event(s)`)
if (Array.isArray(logs.body?.items) && logs.body.items.length > 0) {
  const event = logs.body.items[0]
  for (const field of ['level', 'event', 'message', 'timestamp']) {
    check(`log.${field} is present`, field in event, event[field] === undefined ? 'undefined' : typeof event[field])
  }
}

console.log()
console.log('='.repeat(66))
console.log('FAILURES:', failures)
process.exit(failures ? 1 : 0)
