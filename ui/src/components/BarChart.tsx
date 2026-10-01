import { useId } from 'react'

/**
 * A bar chart, in SVG, with no chart library.
 *
 * ## Why hand-built
 *
 * The bundle carries react-query and react-router and nothing else. A charting
 * library is roughly 50KB gzipped for what this needs: seven bars, one axis, and
 * a label. It also brings its own colour defaults, which would have to be
 * overridden to match the KALIMA palette -- and a chart library that needs its
 * theme overridden is a chart library that will drift from the theme.
 *
 * ## The shape of it
 *
 * Bars, not a line. The data is "how many jobs started on this day" -- a count
 * per day, and a line would imply a continuity between days that does not
 * exist. Zero days are kept as zero-height bars rather than dropped: a gap in
 * the data and a day with no jobs must not look the same.
 *
 * Every dimension is derived from the data rather than fixed, so a busy week and
 * a quiet one both fill the frame.
 */
export interface Bar {
  /** The label under the bar. Kept short by the caller. */
  label: string
  value: number
  /** An optional fuller label, for the tooltip and the accessible name. */
  title?: string
}

export function BarChart({
  bars,
  height = 132,
  /** Spoken instead of the numbers, which a screen reader would read as noise. */
  caption,
}: {
  bars: readonly Bar[]
  height?: number
  caption: string
}) {
  const gradientId = useId()
  if (bars.length === 0) {
    return (
      <p className="empty" style={{ minHeight: height }}>
        هنوز داده‌ای برای نمودار نیست.
      </p>
    )
  }

  // The tallest bar sets the scale, so the chart always uses its full height
  // instead of leaving the top third empty on a quiet week.
  const peak = Math.max(...bars.map((bar) => bar.value), 1)
  // 1.5px of gap between bars, expressed in data units, so it does not change
  // the aspect ratio when the bar count changes.
  const gap = 1.5

  return (
    <figure className="m-0">
      <figcaption className="sr-only">{caption}</figcaption>
      <svg
        viewBox={`0 0 ${bars.length * 10} 100`}
        preserveAspectRatio="none"
        style={{ width: '100%', height, display: 'block', overflow: 'visible' }}
        role="img"
        aria-label={caption}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.28" />
            <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0.04" />
          </linearGradient>
        </defs>
        {bars.map((bar, index) => {
          // A zero bar is drawn as a 1-unit stub rather than nothing at all: an
          // empty slot reads as "no data" and a flat one reads as "none".
          const drawn = Math.max(bar.value, 1)
          const barHeight = (drawn / (peak + gap)) * 100
          return (
            <g key={`${bar.label}-${index}`}>
              <rect
                x={index * 10}
                /* SVG y grows downward, so the bar hangs from the baseline. */
                y={100 - barHeight}
                width={8.5}
                height={barHeight}
                rx={1.5}
                fill={
                  bar.value > 0
                    ? `url(#${gradientId})`
                    : 'var(--color-border)'
                }
                stroke={
                  bar.value > 0 ? 'var(--color-primary)' : 'var(--color-border)'
                }
                strokeWidth={0.7}
              >
                <title>{`${bar.title ?? bar.label}: ${bar.value}`}</title>
              </rect>
            </g>
          )
        })}
        {/* The baseline. One hairline, so the bars sit on something. */}
        <line
          x1={0}
          y1={100}
          x2={bars.length * 10}
          y2={100}
          stroke="var(--color-border)"
          strokeWidth={0.7}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="mt-[var(--spacing-2)] flex justify-between" aria-hidden="true">
        {bars.map((bar, index) => (
          <span
            key={`${bar.label}-label-${index}`}
            className="text-[length:var(--text-caption)] tabular-nums"
            style={{
              color: 'var(--color-text-muted)',
              /* With seven bars in a narrow phone each label gets ~11% of the
                 width, which is about 43px -- enough for a Persian day label at
                 12px, and not enough for a date. The caller sends short ones. */
              flex: '1 1 0',
              minWidth: 0,
              textAlign: 'center',
            }}
          >
            {bar.label}
          </span>
        ))}
      </div>
    </figure>
  )
}
