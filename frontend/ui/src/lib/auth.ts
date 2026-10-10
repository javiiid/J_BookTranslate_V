/**
 * Client side of the auth API (`app/auth/` owns the truth).
 *
 * The pure validators below mirror the server bounds so a typo'd email is
 * caught before a round trip. They are convenience only: the server rechecks
 * everything, and `tests/auth.test.ts` pins the two sides to the same rules.
 */

export interface AuthUser {
  id: number
  email: string
  display_name: string
  created_at: string
}

export interface AuthResponse {
  user: AuthUser
}

export interface AuthMeResponse {
  user: AuthUser
}

export interface AuthSession {
  /** First 16 hex chars of the session hash. Pass back to revoke it. */
  id: string
  created_at: string
  expires_at: string
  current: boolean
}

/** True for an address the server would accept (trimmed, one @, one dot). */
export function validEmail(value: string): boolean {
  const address = value.trim().toLowerCase()
  return address.length > 0 && address.length <= 180 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(address)
}

/** True for a password inside the server's 8..200 length window. */
export function validPassword(value: string): boolean {
  return value.length >= 8 && value.length <= 200
}

/** True for a display name the server would keep (1..100 after trim). */
export function validDisplayName(value: string): boolean {
  const name = value.trim()
  return name.length > 0 && name.length <= 100
}

/** True for a 6-digit login code the server would accept. */
export function validOtpCode(value: string): boolean {
  return /^\d{6}$/.test(value.trim())
}
