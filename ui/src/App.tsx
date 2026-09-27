import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { DashboardPage } from '@/pages/DashboardPage'
import { JobDetailPage } from '@/pages/JobDetailPage'
import { JobListPage } from '@/pages/JobListPage'
import { WorkspacePage } from '@/pages/WorkspacePage'
import { LibraryPage } from '@/pages/LibraryPage'
import { ReaderPage } from '@/pages/ReaderPage'
import { AccountPage } from '@/pages/AccountPage'
import { NotFoundPage } from '@/pages/PendingPage'

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />

        {/* Phase 2: the job monitor. Ported from app/jobs/detail_page.py. */}
        <Route path="/jobs" element={<JobListPage />} />
        <Route path="/jobs/:id" element={<JobDetailPage />} />

        {/* Phase 3: the translation form and the library. */}
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/library" element={<LibraryPage />} />

        {/* Phase 4: the bilingual reader. */}
        <Route path="/reader/:id?" element={<ReaderPage />} />

        {/* Phase 5: account is ported. The landing page is still the Python
            one; it is marketing rather than product surface. */}
        <Route path="/account" element={<AccountPage />} />
        <Route path="/landing" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}
