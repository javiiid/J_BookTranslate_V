import type { Language } from '../i18n/lang.ts'

/**
 * The active UI language for the pure formatters in `format.ts` and the
 * label helpers in `dashboard.ts`.
 *
 * Those modules are `.ts` on purpose (importable by `node --test`, which
 * cannot run hooks), so they cannot call `useLanguage`. The provider writes
 * here on every change instead, and `main.tsx` seeds it before first paint
 * next to the theme. Tests set it directly.
 */
let active: Language = 'fa'

export function getLocale(): Language {
  return active
}

export function setLocale(lang: Language): void {
  active = lang
}

export function localeTag(): string {
  return active === 'fa' ? 'fa-IR' : 'en-US'
}
