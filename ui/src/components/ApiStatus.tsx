import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

type Tone = 'pending' | 'ready' | 'error'

const TONE_STYLE: Record<Tone, string> = {
  pending: 'bg-slate-400',
  ready: 'bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]',
  error: 'bg-red-500',
}

const TONE_TEXT: Record<Tone, string> = {
  pending: 'text-slate-500',
  ready: 'text-emerald-700',
  error: 'text-red-600',
}

/**
 * Provider readiness indicator. Mirrors the dot + label pattern the Python
 * pages use, so the dashboard keeps the same affordance after the port.
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

  return (
    <div
      className="flex items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-xs"
      role="status"
      aria-live="polite"
    >
      <span className={`h-2 w-2 rounded-full ${TONE_STYLE[tone]}`} aria-hidden="true" />
      <span className={TONE_TEXT[tone]}>{message}</span>
    </div>
  )
}
