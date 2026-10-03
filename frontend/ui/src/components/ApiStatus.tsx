import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

type Tone = 'pending' | 'ready' | 'error'

/**
 * Token-driven rather than Tailwind colour classes.
 *
 * The old version hardcoded `bg-emerald-500` and a hand-written rgba() glow,
 * which meant two things: it carried the previous green, and it was the only
 * place in the app with a hardcoded shadow value. Both are now tokens.
 */
const TONE: Record<Tone, { dot: string; text: string; ring: string }> = {
  pending: { dot: 'var(--color-text-muted)', text: 'var(--color-text-muted)', ring: 'transparent' },
  ready: { dot: 'var(--color-success)', text: 'var(--color-success)', ring: 'var(--color-success-subtle)' },
  error: { dot: 'var(--color-error)', text: 'var(--color-error)', ring: 'var(--color-error-subtle)' },
}

/**
 * Provider readiness indicator. The dot is aria-hidden and the label carries
 * the meaning, so the state is not communicated by colour alone.
 */
export function ApiStatus() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const tone: Tone = isPending ? 'pending' : isError ? 'error' : data?.status === 'ready' ? 'ready' : 'error'
  const message = isError ? 'ارتباط با سرور قطع است' : (data?.message ?? 'در حال بررسی…')
  const palette = TONE[tone]

  return (
    <span
      className="badge"
      style={{ paddingInline: 'var(--spacing-3)', paddingBlock: 'var(--spacing-2)' }}
      role="status"
      aria-live="polite"
    >
      <span
        className="state-dot"
        // The ring is what replaced the old glow, and it is a surface colour so
        // it needs no separate shadow token.
        style={{ color: palette.dot, boxShadow: `0 0 0 3px ${palette.ring}` }}
        aria-hidden="true"
      />
      <span style={{ color: palette.text }}>{message}</span>
    </span>
  )
}
