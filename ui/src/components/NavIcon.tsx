import type { SVGProps } from 'react'
import type { NavIconName } from './nav'

/**
 * The icon set.
 *
 * The only place a name becomes a shape. 24px on a 1.75 stroke, `currentColor`
 * so it inherits whatever the theme resolved, and no fill -- these are outlines
 * because a filled glyph at 20px turns to mud in the dark theme.
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
  /** A dashboard: four panes. */
  dashboard: (p) => (
    <Stroke {...p}>
      <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" />
    </Stroke>
  ),
  /** Add a book: a document with a plus. The app's primary action. */
  add: (p) => (
    <Stroke {...p}>
      <path d="M12 6.75v7M8.5 10.25h7" />
      <path d="M5 4.75A1.75 1.75 0 0 1 6.75 3H18a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6.75A1.75 1.75 0 0 1 5 19.25z" />
    </Stroke>
  ),
  /** Convert: two arrows swapping direction. */
  convert: (p) => (
    <Stroke {...p}>
      <path d="M4 8.5h14l-3.5-3.5" />
      <path d="M20 15.5H6l3.5 3.5" />
    </Stroke>
  ),
  /** Watch a translation run: a clock. */
  monitor: (p) => (
    <Stroke {...p}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.25V12l3.25 2.25" />
    </Stroke>
  ),
  /** Library: three spines on a shelf. */
  library: (p) => (
    <Stroke {...p}>
      <path d="M4 5.75A1.75 1.75 0 0 1 5.75 4H8v16H5.75A1.75 1.75 0 0 1 4 18.25z" />
      <path d="M10 4h3.25v16H10z" />
      <path d="M15.25 4h3A1.75 1.75 0 0 1 20 5.75v12.5A1.75 1.75 0 0 1 18.25 20h-3z" />
    </Stroke>
  ),
  /** Read: an open page. */
  reader: (p) => (
    <Stroke {...p}>
      <path d="M12 6.5C10.5 5 8.5 4.5 6 4.5H3.5v13H6c2.5 0 4.5.5 6 2 1.5-1.5 3.5-2 6-2h2.5v-13H18c-2.5 0-4.5.5-6 2z" />
      <path d="M12 6.5v13" />
    </Stroke>
  ),
  /** Account: a person. */
  account: (p) => (
    <Stroke {...p}>
      <circle cx="12" cy="8" r="3.75" />
      <path d="M4.75 20a7.25 7.25 0 0 1 14.5 0" />
    </Stroke>
  ),
}

export function NavIcon({ name, size = 24 }: { name: NavIconName; size?: number | undefined }) {
  const Glyph = GLYPHS[name]
  return <Glyph size={size} />
}
