import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fa } from '@/lib/format'

/**
 * The glossary status panel.
 *
 * Shows how many approved terms the book has, how many drafts are waiting for a
 * decision, and offers the one-call proposal. The important part is what it says
 * when there is nothing: translation still works without a glossary, so the panel
 * warns rather than blocks.
 */
export interface GlossaryPanelProps {
  bookId: number | null
  from: string
  to: string
  model: string
  onPropose: () => void
}

export function GlossaryPanel({ bookId, from, to, model, onPropose }: GlossaryPanelProps) {
  const client = useQueryClient()
  const [message, setMessage] = useState<{ text: string; tone: 'ok' | 'error' } | null>(null)

  const approved = useQuery({
    queryKey: ['glossary', bookId, from, to],
    queryFn: () => api.glossary(bookId as number, from, to),
    enabled: bookId !== null,
  })

  const draft = useQuery({
    queryKey: ['glossary-proposal', bookId, from, to],
    queryFn: () => api.proposal(bookId as number, from, to),
    enabled: bookId !== null,
  })

  const propose = useMutation({
    mutationFn: () =>
      api.proposeTerms(bookId as number, {
        from_lang: from,
        to_lang: to,
        ...(model ? { model } : {}),
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['glossary-proposal', bookId] })
      setMessage({ text: 'پیشنهاد آمادهٔ بازبینی است.', tone: 'ok' })
      onPropose()
    },
    onError: (error) => {
      setMessage({
        text: error instanceof Error ? error.message : 'ساخت پیشنهاد ناموفق بود',
        tone: 'error',
      })
    },
  })

  const approvedCount = approved.data?.terms.length ?? 0
  const draftCount = draft.data?.terms.length ?? 0

  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between gap-2">
        <strong className="text-[length:var(--text-body)]">واژه‌نامهٔ کتاب</strong>
        <span className="badge badge-accent">{fa(approvedCount)} اصطلاح</span>
      </div>

      <p
        className="text-[length:var(--text-label)] leading-7"
        style={{ color: 'var(--color-text-muted)' }}
      >
        واژه‌نامه پیش از ترجمه ساخته می‌شود و شما آن را تأیید می‌کنید؛ حین ترجمه چیزی
        خودکار اضافه نمی‌شود.
      </p>

      {message ? (
        <p
          role={message.tone === 'error' ? 'alert' : 'status'}
          className={`alert ${message.tone === 'ok' ? 'alert-info' : 'alert-error'}`}
        >
          {message.text}
        </p>
      ) : null}

      {bookId === null ? (
        <p className="alert alert-warning">
          ابتدا کتاب را یک‌بار در صف اضافه کنید تا بتوان برایش واژه‌نامه ساخت.
        </p>
      ) : approvedCount > 0 ? (
        <p className="alert alert-info">
          این واژه‌نامه در همهٔ بخش‌ها، از جمله بخش اول، اعمال می‌شود.
        </p>
      ) : draftCount > 0 ? (
        <p className="alert alert-warning">
          {fa(draftCount)} پیشنهاد در انتظار بازبینی است. تا تأیید نکنید، ترجمه بدون
          واژه‌نامه انجام می‌شود.
        </p>
      ) : (
        <p className="alert alert-warning">
          واژه‌نامه‌ای ثبت نشده. بدون آن هم ترجمه انجام می‌شود، اما اصطلاحات یکدست
          نمی‌مانند.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={bookId === null || propose.isPending}
          onClick={() => propose.mutate()}
        >
          {propose.isPending ? 'در حال ساخت…' : 'پیشنهاد واژه‌نامه'}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={bookId === null || draftCount === 0}
          onClick={onPropose}
        >
          بازبینی پیشنهادها
        </button>
      </div>

      {propose.isPending ? (
        <p
          className="text-[length:var(--text-caption)]"
          style={{ color: 'var(--color-text-muted)' }}
          role="status"
        >
          در حال خواندن متن کتاب و ساخت پیشنهاد. یک درخواست است و ممکن است ۲۰ تا ۶۰ ثانیه
          طول بکشد.
        </p>
      ) : null}
    </div>
  )
}
