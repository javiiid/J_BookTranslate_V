import type { SVGProps } from 'react'
import type { NavIconName } from './nav'

/**
 * The icon set.
 *
 * The only place a name becomes a shape. 24px on a 1.75 stroke, `currentColor`
 * so it inherits whatever the theme resolved, and no fill -- these are outlines
 * because a filled glyph at 20px turns to mud in the dark theme.
 *
 * The drawings are Lucide's (lucide-static 0.469.0, ISC licence -- free to
 * use and modify, no attribution in the UI), inlined here rather than taken
 * through the `lucide-react` package: this project ships zero runtime UI
 * dependencies, and seven icons do not justify one. The wrapper below is the
 * project's own (1.75 stroke, hidden from assistive tech); only the inner
 * path data comes from Lucide.
 *
 * `aria-hidden` on every one: the visible label beside each icon already names
 * the destination, so announcing the shape as well would read it twice.
 */
export interface NavIconProps extends Omit<SVGProps<SVGSVGElement>, 'children'> {
  /**
   * Rendered size in pixels.
   *
   * Declared as possibly-undefined explicitly because the project compiles with
   * `exactOptionalPropertyTypes`, where `size?: number` refuses a
   * `number | undefined` from a caller that forwards an optional prop. The
   * default below is what makes the value a `number` by the time it is used.
   */
  size?: number | undefined
}

type Glyph = (props: NavIconProps) => React.JSX.Element

function Stroke({ size = 24, children, ...rest }: NavIconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  )
}

const GLYPHS: Record<NavIconName, Glyph> = {
  /** A dashboard: four panes of unequal weight (Lucide `layout-dashboard`). */
  dashboard: (p) => (
    <Stroke {...p}>
      <rect width="7" height="9" x="3" y="3" rx="1" />
      <rect width="7" height="5" x="14" y="3" rx="1" />
      <rect width="7" height="9" x="14" y="12" rx="1" />
      <rect width="7" height="5" x="3" y="16" rx="1" />
    </Stroke>
  ),
  /** Add a book: a document with a plus (Lucide `book-plus`). The app's primary action. */
  add: (p) => (
    <Stroke {...p}>
      <path d="M12 7v6" />
      <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20" />
      <path d="M9 10h6" />
    </Stroke>
  ),
  /** Convert: two arrows swapping direction (Lucide `arrow-right-left`). */
  convert: (p) => (
    <Stroke {...p}>
      <path d="m16 3 4 4-4 4" />
      <path d="M20 7H4" />
      <path d="m8 21-4-4 4-4" />
      <path d="M4 17h16" />
    </Stroke>
  ),
  /** Watch a translation run: a pulse (Lucide `activity`). */
  monitor: (p) => (
    <Stroke {...p}>
      <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2" />
    </Stroke>
  ),
  /** Library: four leaning spines (Lucide `library`). */
  library: (p) => (
    <Stroke {...p}>
      <path d="m16 6 4 14" />
      <path d="M12 6v14" />
      <path d="M8 8v12" />
      <path d="M4 4v16" />
    </Stroke>
  ),
  /** Read: an open book (Lucide `book-open`). */
  reader: (p) => (
    <Stroke {...p}>
      <path d="M12 7v14" />
      <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />
    </Stroke>
  ),
  /** Account: a person in a circle (Lucide `circle-user-round`). */
  account: (p) => (
    <Stroke {...p}>
      <path d="M18 20a6 6 0 0 0-12 0" />
      <circle cx="12" cy="10" r="4" />
      <circle cx="12" cy="12" r="10" />
    </Stroke>
  ),
  /** Help: a question mark in a circle (Lucide `circle-help`). */
  help: (p) => (
    <Stroke {...p}>
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <path d="M12 17h.01" />
    </Stroke>
  ),
}

export function NavIcon({
  name,
  size = 24,
  strokeWidth,
}: {
  name: NavIconName
  size?: number | undefined
  strokeWidth?: number | undefined
}) {
  const Glyph = GLYPHS[name]
  /* Spread only when given. `Stroke` puts `...rest` after its own default, so an
     explicit `strokeWidth: undefined` would overwrite 1.75 with nothing and the
     icon would be drawn at the SVG default of 1. */
  return <Glyph size={size} {...(strokeWidth === undefined ? {} : { strokeWidth })} />
}
