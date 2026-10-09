export type Language = 'fa' | 'en'
export type Direction = 'rtl' | 'ltr'

/**
 * Shared with the Python pages (`jbook-language` in `app/core/web_i18n.py`),
 * for the same reason the theme key is shared: a reader who picks English on
 * one UI must not get Persian back on the other. Renaming it would split the
 * preference in two, silently.
 */
export const LANGUAGE_KEY = 'jbook-language'
