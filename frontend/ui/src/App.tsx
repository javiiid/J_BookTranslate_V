import { Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { DashboardPage } from '@/pages/DashboardPage'
import { JobDetailPage } from '@/pages/JobDetailPage'
import { JobListPage } from '@/pages/JobListPage'
import { WorkspacePage } from '@/pages/WorkspacePage'
import { LibraryPage } from '@/pages/LibraryPage'
import { ReaderPage } from '@/pages/ReaderPage'
import { AccountPage } from '@/pages/AccountPage'
import { AuthPage } from '@/pages/AuthPage'
import { LandingPage } from '@/pages/LandingPage'
import { NotFoundPage } from '@/pages/PendingPage'
import { ConversionPage } from '@/pages/ConversionPage'
import { CalibrationPage } from '@/pages/CalibrationPage'
import { HelpPage } from '@/pages/HelpPage'
import { HelpArticlePage } from '@/pages/HelpArticlePage'
import { HelpSearchDialog } from '@/components/help/HelpSearchDialog'
import { ConversionProvider } from '@/components/conversion/ConversionProvider'

        {/* Phase 4: the bilingual reader. Ported from `app/reader/page.py`
            (settings, glossary panel, paragraph pairing, columns mode).
            Chapter images are still backend bytes under
            `/reader/<id>/asset/<path>` -- in dev the vite proxy's `bypass`
            lets those through while the SPA shell owns the page; in
            production one origin serves both. */}
        <Route path="/reader/:id" element={<ReaderPage />} />

export function App() {
  const { pathname } = useLocation()
  const bare = pathname.replace(/\/+$/, '')
  if (bare === '/landing' || bare === '/login' || bare === '/signup') {
    // Standalone surfaces, not product surface: no rail, no bottom bar.
    // A login form inside the app chrome would read as already being in.
    return (
      <ConversionProvider>
        <Routes>
          <Route path="/landing" element={<LandingPage />} />
          <Route path="/login" element={<AuthPage />} />
          <Route path="/signup" element={<AuthPage />} />
        </Routes>
      </ConversionProvider>
    )
  }
  return (
    <ConversionProvider>
    <AppShell>
      <HelpSearchDialog />
      <Routes>
        <Route path="/" element={<DashboardPage />} />

        {/* Phase 2: the job monitor. Ported from app/jobs/detail_page.py. */}
        <Route path="/jobs" element={<JobListPage />} />
        <Route path="/jobs/:id" element={<JobDetailPage />} />

        {/* Phase 3: the translation form and the library.
            `/workspace` is intake only now: it stores the upload and opens a
            calibration workshop at `/calibrations/:id`, where the voice and the
            glossary are settled on real samples before the book is translated. */}
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/calibrations/:id" element={<CalibrationPage />} />
        <Route path="/convert" element={<ConversionPage />} />
        <Route path="/library" element={<LibraryPage />} />

        {/* Phase 5b: the help center. `/help` is the hub (query string
            carries `q`, `cat` and `faq`); every article is a stable
            `/help/articles/:slug` so links survive refresh and sharing. */}
        <Route path="/help" element={<HelpPage />} />
        <Route path="/help/articles/:slug" element={<HelpArticlePage />} />

        {/* Phase 4: the bilingual reader. Ported from `app/reader/page.py`
            (settings, glossary panel, paragraph pairing, columns mode).
            Chapter images are still backend bytes under
            `/reader/<id>/asset/<path>` -- in dev the vite proxy's `bypass`
            lets those through while the SPA shell owns the page; in
            production one origin serves both. */}
        <Route path="/reader/:id" element={<ReaderPage />} />

        {/* Phase 5: account, and the landing page.
            `/landing` used to redirect here because the Python backend served
            that path as 65KB of server-rendered HTML and won the proxy match
            ahead of the SPA fallback. The proxy is now `/api` and `/downloads`
            only, so the path belongs to React and the page exists. */}
        <Route path="/account" element={<AccountPage />} />
        <Route path="/login" element={<AuthPage />} />
        <Route path="/signup" element={<AuthPage />} />
        <Route path="/landing" element={<LandingPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
    </ConversionProvider>
  )
}
