import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { DashboardPage } from '@/pages/DashboardPage'
import { NotFoundPage, PendingPage } from '@/pages/PendingPage'

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        {/* Phase 2 onwards. Kept as real routes now so navigation never 404s
            while the port is in progress. */}
        <Route path="/jobs" element={<PendingPage title="پایش ترجمه" />} />
        <Route path="/jobs/:id" element={<PendingPage title="پایش یک کار" />} />
        <Route path="/library" element={<PendingPage title="کتابخانه" />} />
        <Route path="/reader" element={<PendingPage title="مطالعه" />} />
        <Route path="/account" element={<PendingPage title="پنل کاربری" />} />
        <Route path="/landing" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}
