import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'

interface NavItem {
  to: string
  label: string
  icon: string
}

const NAV: NavItem[] = [
  { to: '/', label: 'داشبورد', icon: '◧' },
  { to: '/jobs', label: 'پایش ترجمه', icon: '◷' },
  { to: '/library', label: 'کتابخانه', icon: '▣' },
  { to: '/reader', label: 'مطالعه', icon: '❐' },
  { to: '/account', label: 'پنل کاربری', icon: '◈' },
]

export function Sidebar() {
  return (
    <aside
      className="fixed inset-y-4 right-4 z-40 flex w-60 flex-col gap-4 rounded-[20px] border p-4"
      style={{ background: 'var(--surface)', borderColor: 'var(--line)' }}
      aria-label="ناوبری اصلی"
    >
      <div
        className="flex items-center gap-3 border-b pb-3"
        style={{ borderColor: 'var(--line)' }}
      >
        <span
          className="grid h-9 w-9 place-items-center rounded-xl text-white"
          style={{ background: 'linear-gradient(140deg,var(--blue),var(--purple))' }}
          aria-hidden="true"
        >
          文
        </span>
        <span className="min-w-0">
          <strong className="block truncate text-sm">J Book Translate</strong>
          <small className="block text-[10px]" style={{ color: 'var(--muted)' }}>
            Translation Studio
          </small>
        </span>
      </div>

      <nav className="grid gap-1">
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [
                'flex items-center gap-2 rounded-[10px] px-3 py-2.5 text-start text-xs font-semibold transition-colors',
                isActive ? 'text-[var(--blue)]' : 'text-[var(--muted)] hover:text-[var(--ink)]',
              ].join(' ')
            }
            style={({ isActive }) =>
              isActive ? { background: 'var(--blue-soft)' } : undefined
            }
          >
            <span className="w-5 text-center" aria-hidden="true">
              {icon}
            </span>
            {label}
          </NavLink>
        ))}
      </nav>

      <p className="mt-auto text-[10px] leading-5" style={{ color: 'var(--muted)' }}>
        رابط جدید روی همان API پایتون کار می‌کند.
        <br />
        بک‌اند دست‌نخورده باقی مانده است.
      </p>
    </aside>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div>
      <Sidebar />
      <div className="mr-[272px] min-h-dvh">{children}</div>
    </div>
  )
}
