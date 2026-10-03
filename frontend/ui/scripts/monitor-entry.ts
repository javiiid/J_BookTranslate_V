/**
 * Build entry for `render-monitor.mjs`.
 *
 * Separate from the other harnesses because the monitor pages need the job and
 * chunk payloads seeded, and pulling them into the page harness would make that
 * one slower for no benefit.
 */
export { JobListPage } from '../src/pages/JobListPage'
export { JobDetailPage } from '../src/pages/JobDetailPage'
export { AppShell } from '../src/components/AppShell'
