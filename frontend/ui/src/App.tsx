import { Route, Routes, Link } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { DashboardPage } from '@/pages/DashboardPage'
import { JobDetailPage } from '@/pages/JobDetailPage'
import { JobListPage } from '@/pages/JobListPage'
import { WorkspacePage } from '@/pages/WorkspacePage'
import { LibraryPage } from '@/pages/LibraryPage'
/* The React reader is not mounted: `/reader` is proxied to the Python page
   while that port catches up. The import is kept and marked unused rather than
   deleted, so putting the port back is uncommenting one line instead of
   rewriting it -- and `tests/routing.test.ts` fails if the file is deleted
   outright, which is the mistake this comment exists to prevent. */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { ReaderPage } from '@/pages/ReaderPage'
void ReaderPage
import { AccountPage } from '@/pages/AccountPage'
import { LandingPage } from '@/pages/LandingPage'
import { NotFoundPage } from '@/pages/PendingPage'
import { ConversionPage } from '@/pages/ConversionPage'
import { ConversionProvider } from '@/components/conversion/ConversionProvider'

/**
 * What a visitor sees if `/reader` reaches React at all.
 *
 * It should not, normally: the path is proxied to the Python page, and Vite's
 * proxy runs before the SPA fallback. So this renders only when the handover is
 * undone, or when the proxy is not matching for some other reason.
 *
 * It says so, rather than rendering `NotFoundPage`. A 404 on a path that
 * exists and is linked from the dashboard, the library and the job list reads
 * as a bug; this reads as the arrangement it is, and names the way to reach
 * the React port directly.
 */
function ReaderHandedOver() {
  return (
    <main className="page" dir="rtl">
      <h1 className="mb-[var(--spacing-3)] text-[length:var(--text-h2)] font-extrabold">
        خواننده به نسخهٔ پایتون سپرده شده
      </h1>
      <p
        className="mb-[var(--spacing-4)] max-w-[44rem] text-[length:var(--text-body)]"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        مسیر <code>/reader</code> به صفحهٔ پایتون پروکسی می‌شود، چون نسخهٔ اصلی کامل‌تر است. اگر
        این صفحه را می‌بینید، یعنی پروکسی در حال کار نیست.
      </p>
      <p className="mb-[var(--spacing-5)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-muted)' }}>
        نسخهٔ React هنوز در <code>src/pages/ReaderPage.tsx</code> هست و کامل نیست: جفت‌سازی پاراگراف،
        پنل واژه‌نامه و تنظیمات در نسخهٔ پایتون هست و در این یکی نه.
      </p>
      <div className="control-row">
        <Link to="/library" className="btn btn-primary">
          کتابخانه
        </Link>
        <Link to="/" className="btn btn-secondary">
          داشبورد
        </Link>
      </div>
    </main>
  )
}

export function App() {
  return (
    <ConversionProvider>
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />

        {/* Phase 2: the job monitor. Ported from app/jobs/detail_page.py. */}
        <Route path="/jobs" element={<JobListPage />} />
        <Route path="/jobs/:id" element={<JobDetailPage />} />

        {/* Phase 3: the translation form and the library. */}
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/convert" element={<ConversionPage />} />
        <Route path="/library" element={<LibraryPage />} />

        {/* Phase 4: the bilingual reader.

            TEMPORARILY NOT HERE. The path is proxied to the Python page instead
            -- see the note in `vite.config.ts`. The React port is kept at
            `src/pages/ReaderPage.tsx` and is still exported, so putting it back
            is deleting two lines rather than rewriting the port.

            The route is not merely left undeclared: an undeclared `/reader`
            would fall through to the catch-all and render `NotFoundPage` if the
            proxy ever stopped matching, which looks like a broken link rather
            than a deliberate handover. The element below says what is going on
            and how to get to the other one. */}
        <Route path="/reader/*" element={<ReaderHandedOver />} />

        {/* Phase 5: account, and the landing page.
            `/landing` used to redirect here because the Python backend served
            that path as 65KB of server-rendered HTML and won the proxy match
            ahead of the SPA fallback. The proxy is now `/api` and `/downloads`
            only, so the path belongs to React and the page exists. */}
        <Route path="/account" element={<AccountPage />} />
        <Route path="/landing" element={<LandingPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
    </ConversionProvider>
  )
}
