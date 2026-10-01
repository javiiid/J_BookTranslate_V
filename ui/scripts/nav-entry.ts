/**
 * Build entry for `render-mobile-nav.mjs`.
 *
 * A separate entry because the harness builds one library at a time and this
 * one needs only the bar, not the pages. It exists as a file rather than being
 * assembled inline so Vite resolves the `@/` alias the same way the app does.
 */
export { MobileNav } from '../src/components/MobileNav'
