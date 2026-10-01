/**
 * Entry point for the contrast audit build.
 *
 * A real file rather than a virtual module: the virtual form did not resolve as
 * a lib entry, and the audit needs the same JSX the browser runs, not a
 * hand-written approximation of it.
 */
export { EstimateModal } from '../src/components/estimate/EstimateModal'
export { ReaderPage } from '../src/pages/ReaderPage'
export { AccountPage } from '../src/pages/AccountPage'
export { DashboardPage } from '../src/pages/DashboardPage'
export { JobListPage } from '../src/pages/JobListPage'
export { WorkspacePage } from '../src/pages/WorkspacePage'
export { LibraryPage } from '../src/pages/LibraryPage'
export { LandingPage } from '../src/pages/LandingPage'
export { AppShell } from '../src/components/AppShell'
