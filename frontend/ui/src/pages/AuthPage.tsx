/**
 * Login / signup, in React — complete against the backend auth API.
 *
 * Three ways in: password (`/login`, `/signup` tabs), email code, and
 * Google/Apple OAuth. The session rides an HttpOnly cookie (`app/auth/` owns
 * the truth), so this page never sees, stores, or forwards a token -- it
 * posts forms and navigates on `{user}`.
 *
 * OAuth leaves the SPA on purpose: the start endpoint answers `{auth_url}`
 * as JSON, the page navigates there top-level, and the callback sets the
 * cookie and 302s to /library -- a cookie set on an XHR would never stick
 * the same way.
 *
 * Already logged in and landing here anyway (a stale bookmark, the back
 * button) goes to the session panel instead of a form: a login form behind
 * an active session is how "am I in or out?" confusion starts. The panel
 * lists signed-in devices with revoke, revoke-all, and change-password --
 * the leaked-cookie recovery path.
 *
 * Rules honoured: `.page` gutter, tokens only, `dir` from the provider,
 * `role="alert"` on the error, 44px rows, `prefers-reduced-motion` untouched
 * (no motion here at all), zero new dependencies.
 */
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { KalimaMark } from '@/components/AppShell'
import { api, ApiError } from '@/lib/api.ts'
import { validDisplayName, validEmail, validOtpCode, validPassword } from '@/lib/auth.ts'
import type { AuthSession, AuthUser } from '@/lib/auth.ts'
import { useLanguage } from '@/i18n/useLanguage.ts'
import './auth.css'

type Mode = 'login' | 'signup'
type Method = 'password' | 'code'

export function AuthPage(): React.JSX.Element {
  const { t, dir } = useLanguage()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>(pathname.startsWith('/signup') ? 'signup' : 'login')
  const [method, setMethod] = useState<Method>('password')
  const [email, setEmail] = useState<string>('')
  const [password, setPassword] = useState<string>('')
  const [displayName, setDisplayName] = useState<string>('')
  const [showPassword, setShowPassword] = useState<boolean>(false)
  const [code, setCode] = useState<string>('')
  const [codeSent, setCodeSent] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState<boolean>(false)
  const [sessions, setSessions] = useState<AuthSession[] | null>(null)
  const [currentPassword, setCurrentPassword] = useState<string>('')
  const [newPassword, setNewPassword] = useState<string>('')
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

  useEffect(() => {
    if (session === undefined || session === null) {
      setSessions(null)
      return
    }
    let cancelled = false
    void api
      .authSessions()
      .then((response) => {
        if (!cancelled) setSessions(response.items)
      })
      .catch(() => {
        if (!cancelled) setSessions([])
      })
    return () => {
      cancelled = true
    }
  }, [session])

  function fail(failure: unknown): void {
    setError(failure instanceof ApiError ? failure.message : t('auth.serverError'))
  }

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
    setNotice(null)
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
      fail(failure)
    } finally {
      setBusy(false)
    }
  }

  async function sendCode(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (busy) return
    if (!validEmail(email)) {
      setError(t('auth.badEmail'))
      return
    }
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      await api.authRequestEmailCode({ email: email.trim() })
      setCodeSent(true)
      setNotice(t('auth.codeSent'))
    } catch (failure) {
      fail(failure)
    } finally {
      setBusy(false)
    }
  }

  async function verifyCode(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (busy) return
    if (!validEmail(email) || !validOtpCode(code)) {
      setError(!validEmail(email) ? t('auth.badEmail') : t('auth.badCode'))
      return
    }
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      const response = await api.authVerifyEmailCode({ email: email.trim(), code: code.trim() })
      setSession(response.user)
      navigate('/', { replace: true })
    } catch (failure) {
      fail(failure)
    } finally {
      setBusy(false)
    }
  }

  async function startOAuth(provider: 'google' | 'apple'): Promise<void> {
    if (busy) return
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      const started = await api.authOAuthStart(provider)
      window.location.href = started.auth_url
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 422) {
        setError(t('auth.oauthUnavailable'))
      } else {
        fail(failure)
      }
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
      setSessions(null)
      setBusy(false)
    }
  }

  async function revokeOne(id: string): Promise<void> {
    if (busy) return
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      await api.authRevokeSession({ session_id: id })
      setSessions((items) => (items ?? []).filter((item) => item.id !== id))
    } catch (failure) {
      fail(failure)
    } finally {
      setBusy(false)
    }
  }

  async function revokeOthers(): Promise<void> {
    if (busy) return
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      const response = await api.authRevokeAll()
      setSessions((items) => (items ?? []).filter((item) => item.current))
      setNotice(t('auth.revokedClosed', { count: response.closed }))
    } catch (failure) {
      fail(failure)
    } finally {
      setBusy(false)
    }
  }

  async function changePassword(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (busy) return
    if (!validPassword(currentPassword) || !validPassword(newPassword)) {
      setError(t('auth.badPassword'))
      return
    }
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      await api.authChangePassword({ current_password: currentPassword, new_password: newPassword })
      setCurrentPassword('')
      setNewPassword('')
      setNotice(t('auth.changed'))
      const response = await api.authSessions()
      setSessions(response.items)
    } catch (failure) {
      fail(failure)
    } finally {
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

              <h2 className="mt-[var(--spacing-5)] text-[length:var(--text-small)] font-extrabold">
                {t('auth.sessionsTitle')}
              </h2>
              <p className="mt-[var(--spacing-1)] text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
                {t('auth.sessionsSub')}
              </p>
              {sessions === null ? (
                <div className="skeleton mt-[var(--spacing-3)]" style={{ height: 64 }} role="status" aria-label={t('auth.sending')} />
              ) : sessions.length === 0 ? null : (
                <ul className="mt-[var(--spacing-3)]">
                  {sessions.map((item) => (
                    <li key={item.id} className="flex min-w-0 items-center gap-[var(--spacing-2)]">
                      <span dir="ltr" className="min-w-0 flex-1 truncate text-[length:var(--text-small)]">
                        {item.id}
                      </span>
                      {item.current ? (
                        <span className="text-[length:var(--text-caption)]" style={{ color: 'var(--color-success)' }}>
                          {t('auth.currentDevice')}
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-ghost"
                          disabled={busy}
                          onClick={() => void revokeOne(item.id)}
                        >
                          {t('auth.revoke')}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <div className="control-row mt-[var(--spacing-3)]">
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void revokeOthers()}>
                  {t('auth.revokeAll')}
                </button>
              </div>

              <h2 className="mt-[var(--spacing-5)] text-[length:var(--text-small)] font-extrabold">
                {t('auth.changeTitle')}
              </h2>
              {notice !== null ? (
                <p role="status" className="alert alert-success mt-[var(--spacing-3)]">
                  {notice}
                </p>
              ) : null}
              {error !== null ? (
                <p role="alert" className="alert alert-error mt-[var(--spacing-3)]">
                  {error}
                </p>
              ) : null}
              <form className="auth-form" onSubmit={(event) => void changePassword(event)}>
                <div className="auth-field">
                  <label className="label" htmlFor="auth-current">
                    {t('auth.currentPassword')}
                  </label>
                  <input
                    id="auth-current"
                    className="field"
                    type="password"
                    dir="ltr"
                    autoComplete="current-password"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                    disabled={busy}
                  />
                </div>
                <div className="auth-field">
                  <label className="label" htmlFor="auth-new">
                    {t('auth.newPassword')}
                  </label>
                  <input
                    id="auth-new"
                    className="field"
                    type="password"
                    dir="ltr"
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    disabled={busy}
                  />
                </div>
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {busy ? t('auth.sending') : t('auth.changeSubmit')}
                </button>
              </form>
            </>
          ) : (
            <>
          <h1 className="mt-[var(--spacing-4)] text-[length:var(--text-h2)] font-extrabold">
            {method === 'code' ? t('auth.codeTitle') : mode === 'signup' ? t('auth.signupTitle') : t('auth.loginTitle')}
          </h1>
          <p className="mt-[var(--spacing-1)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
            {method === 'code' ? t('auth.codeSub') : mode === 'signup' ? t('auth.signupSub') : t('auth.loginSub')}
          </p>

          <div className="auth-tabs mt-[var(--spacing-4)]" role="group" aria-label={t('auth.loginTab')}>
            {(['password', 'code'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                className="auth-tab"
                aria-pressed={method === tab}
                onClick={() => {
                  setMethod(tab)
                  setError(null)
                  setNotice(null)
                }}
              >
                {tab === 'code' ? t('auth.codeTab') : t('auth.loginTab')}
              </button>
            ))}
          </div>

          {method === 'password' ? (
            <div className="auth-tabs mt-[var(--spacing-3)]" role="group" aria-label={t('auth.signupTab')}>
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
          ) : null}

          {error !== null ? (
            <p role="alert" className="alert alert-error mt-[var(--spacing-3)]">
              {error}
            </p>
          ) : null}
          {notice !== null ? (
            <p role="status" className="alert alert-success mt-[var(--spacing-3)]">
              {notice}
            </p>
          ) : null}

          {method === 'password' ? (
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
          ) : (
            <>
              <form className="auth-form" onSubmit={(event) => void sendCode(event)}>
                <div className="auth-field">
                  <label className="label" htmlFor="auth-code-email">
                    {t('auth.email')}
                  </label>
                  <input
                    id="auth-code-email"
                    className="field"
                    type="email"
                    dir="ltr"
                    autoComplete="email"
                    placeholder={t('auth.emailPh')}
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    disabled={busy}
                  />
                </div>
                <button type="submit" className="btn btn-secondary" disabled={busy}>
                  {busy ? t('auth.sending') : t('auth.sendCode')}
                </button>
              </form>
              {codeSent ? (
                <form className="auth-form" onSubmit={(event) => void verifyCode(event)}>
                  <div className="auth-field">
                    <label className="label" htmlFor="auth-code">
                      {t('auth.code')}
                    </label>
                    <input
                      id="auth-code"
                      className="field"
                      type="text"
                      dir="ltr"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      placeholder={t('auth.codePh')}
                      value={code}
                      onChange={(event) => setCode(event.target.value)}
                      disabled={busy}
                    />
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={busy}>
                    {busy ? t('auth.sending') : t('auth.verifyCode')}
                  </button>
                </form>
              ) : null}
            </>
          )}

          <p className="mt-[var(--spacing-4)] text-center text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
            {t('auth.orDivider')}
          </p>
          <div className="control-row mt-[var(--spacing-2)]">
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void startOAuth('google')}>
              {t('auth.google')}
            </button>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void startOAuth('apple')}>
              {t('auth.apple')}
            </button>
          </div>

          {method === 'password' ? (
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
          ) : null}
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
