/**
 * Local login / signup, in React.
 *
 * One page, two modes: `/login` and `/signup` render it with different
 * starting tabs. The session rides an HttpOnly cookie (`app/auth/` owns
 * the truth), so this page never sees, stores, or forwards a token -- it
 * posts the form and navigates on `{user}`.
 *
 * Already logged in and landing here anyway (a stale bookmark, the back
 * button) goes to the dashboard: a login form behind an active session is
 * how "am I in or out?" confusion starts.
 *
 * Rules honoured: `.page` gutter, tokens only, `dir` from the provider,
 * `role="alert"` on the error, 44px rows, `prefers-reduced-motion` untouched
 * (no motion here at all), zero new dependencies.
 */
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { KalimaMark } from '@/components/AppShell'
import { api, ApiError } from '@/lib/api.ts'
import { validDisplayName, validEmail, validPassword } from '@/lib/auth.ts'
import type { AuthUser } from '@/lib/auth.ts'
import { useLanguage } from '@/i18n/useLanguage.ts'
import './auth.css'

type Mode = 'login' | 'signup'

export function AuthPage(): React.JSX.Element {
  const { t, dir } = useLanguage()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>(pathname.startsWith('/signup') ? 'signup' : 'login')
  const [email, setEmail] = useState<string>('')
  const [password, setPassword] = useState<string>('')
  const [displayName, setDisplayName] = useState<string>('')
  const [showPassword, setShowPassword] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<boolean>(false)
  /* undefined = still checking; null = no session; a user = logged in. */
  const [session, setSession] = useState<AuthUser | null | undefined>(undefined)

  /* An active session turns this page into a session panel instead of a form:
     a login form behind a login is how "am I in or out?" confusion starts. */
  useEffect(() => {
    let cancelled = false
    void api
      .authMe()
      .then((me) => {
        if (!cancelled) setSession(me.user)
      })
      .catch(() => {
        if (!cancelled) setSession(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (busy) return
    if (!validEmail(email)) {
      setError(t('auth.badEmail'))
      return
    }
    if (!validPassword(password)) {
      setError(t('auth.badPassword'))
      return
    }
    if (mode === 'signup' && !validDisplayName(displayName)) {
      setError(t('auth.badName'))
      return
    }
    setError(null)
    setBusy(true)
    try {
      const trimmed = email.trim()
      const response =
        mode === 'signup'
          ? await api.authSignup({ email: trimmed, password, display_name: displayName.trim() })
          : await api.authLogin({ email: trimmed, password })
      setSession(response.user)
      navigate('/', { replace: true })
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : t('auth.serverError'))
    } finally {
      setBusy(false)
    }
  }

  async function logout(): Promise<void> {
    setBusy(true)
    try {
      await api.authLogout()
    } catch {
      /* The cookie is cleared server-side on success; a network failure
         leaves it, and the next me-check reports the truth either way. */
    } finally {
      setSession(null)
      setBusy(false)
    }
  }

  return (
    <main className="page" dir={dir}>
      <div className="auth-shell">
        <div className="surface-card min-w-0 p-[var(--spacing-5)]">
          <span className="flex min-w-0 items-center gap-[var(--spacing-3)]">
            <KalimaMark size={36} />
            <span className="min-w-0">
              <strong className="block text-[length:var(--text-small)] tracking-wide">KALIMA</strong>
              <small
                className="block text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {t('landing.brandTag')}
              </small>
            </span>
          </span>

          {session === undefined ? (
            <div className="skeleton mt-[var(--spacing-4)]" style={{ height: 220 }} role="status" aria-label={t('auth.sending')} />
          ) : session !== null ? (
            <>
              <h1 className="mt-[var(--spacing-4)] text-[length:var(--text-h2)] font-extrabold">
                {t('auth.sessionTitle')}
              </h1>
              <p className="mt-[var(--spacing-1)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
                {session.display_name} · <span dir="ltr">{session.email}</span>
              </p>
              <div className="control-row mt-[var(--spacing-4)]">
                <Link to="/" className="btn btn-primary">
                  {t('auth.dashboard')}
                </Link>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void logout()}>
                  {t('auth.logout')}
                </button>
              </div>
            </>
          ) : (
            <>
          <h1 className="mt-[var(--spacing-4)] text-[length:var(--text-h2)] font-extrabold">
            {mode === 'signup' ? t('auth.signupTitle') : t('auth.loginTitle')}
          </h1>
          <p className="mt-[var(--spacing-1)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
            {mode === 'signup' ? t('auth.signupSub') : t('auth.loginSub')}
          </p>

          <div className="auth-tabs mt-[var(--spacing-4)]" role="group" aria-label={t('auth.loginTab')}>
            {(['login', 'signup'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                className="auth-tab"
                aria-pressed={mode === tab}
                onClick={() => {
                  setMode(tab)
                  setError(null)
                }}
              >
                {tab === 'login' ? t('auth.loginTab') : t('auth.signupTab')}
              </button>
            ))}
          </div>

          {error !== null ? (
            <p role="alert" className="alert alert-error mt-[var(--spacing-3)]">
              {error}
            </p>
          ) : null}

          <form className="auth-form" onSubmit={(event) => void submit(event)}>
            <div className="auth-field">
              <label className="label" htmlFor="auth-email">
                {t('auth.email')}
              </label>
              <input
                id="auth-email"
                className="field"
                type="email"
                dir="ltr"
                autoComplete={mode === 'signup' ? 'email' : 'username'}
                placeholder={t('auth.emailPh')}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={busy}
              />
            </div>
            {mode === 'signup' ? (
              <div className="auth-field">
                <label className="label" htmlFor="auth-name">
                  {t('auth.displayName')}
                </label>
                <input
                  id="auth-name"
                  className="field"
                  type="text"
                  autoComplete="nickname"
                  placeholder={t('auth.namePh')}
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  disabled={busy}
                />
              </div>
            ) : null}
            <div className="auth-field">
              <label className="label" htmlFor="auth-password">
                {t('auth.password')}
              </label>
              <div className="auth-password-row">
                <input
                  id="auth-password"
                  className="field min-w-0"
                  type={showPassword ? 'text' : 'password'}
                  dir="ltr"
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={busy}
                />
                <button
                  type="button"
                  className="btn btn-ghost"
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((visible) => !visible)}
                >
                  {showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
                </button>
              </div>
            </div>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? t('auth.sending') : mode === 'signup' ? t('auth.submitSignup') : t('auth.submitLogin')}
            </button>
          </form>

          <p className="mt-[var(--spacing-4)] text-center text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
            {mode === 'signup' ? t('auth.haveAccount') : t('auth.noAccount')}{' '}
            <button
              type="button"
              className="btn btn-ghost"
              style={{ minHeight: '44px', paddingInline: 'var(--spacing-2)' }}
              onClick={() => {
                setMode(mode === 'signup' ? 'login' : 'signup')
                setError(null)
              }}
            >
              {mode === 'signup' ? t('auth.loginTab') : t('auth.signupTab')}
            </button>
          </p>
          <p className="mt-[var(--spacing-2)] text-center text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
            <Link to="/landing">{t('landing.nav.product')}</Link>
          </p>
            </>
          )}
        </div>
      </div>
    </main>
  )
}
