import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { GlossaryTerm } from '@/lib/api'
import { fa } from '@/lib/format'
import { key } from '@/lib/terms'

/**
 * Glossary review.
 *
 * Ported from `app/glossary/proposal_page.py`. A proposal is a *draft*: nothing
 * reaches the live glossary until the user decides, and only the ticked terms
 * are promoted. The rejected ones are dropped rather than kept, because a
 * glossary is a decision rather than a suggestion.
 *
 * The dialog is a native `<dialog>`-shaped overlay rather than the browser
 * element, so focus trapping and Escape are handled explicitly below.
 */
export interface GlossaryReviewProps {
  bookId: number
  from: string
  to: string
  onClose: () => void
  onApproved: (message: string) => void
  onError: (message: string) => void
}

const KIND_FA: Record<string, string> = {
  person: 'شخص',
  place: 'مکان',
  organization: 'سازمان',
  title: 'عنوان',
  term: 'اصطلاح',
}

export function GlossaryReview({
  bookId,
  from,
  to,
  onClose,
  onApproved,
  onError,
}: GlossaryReviewProps) {
  const client = useQueryClient()
  const proposal = useQuery({
    queryKey: ['glossary-proposal', bookId, from, to],
    queryFn: () => api.proposal(bookId, from, to),
  })

  // Edits are local until approved, so a cancelled review changes nothing.
  const [rows, setRows] = useState<GlossaryTerm[] | null>(null)
  const [kept, setKept] = useState<Set<string>>(() => new Set())

  const terms = rows ?? proposal.data?.terms ?? []
  const pristine = rows === null

  const approve = useMutation({
    mutationFn: () =>
      api.approveProposal(bookId, {
        from_lang: from,
        to_lang: to,
        origin: 'preflight',
        approved: [...kept],
      }),
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: ['glossary-proposal', bookId] })
      void client.invalidateQueries({ queryKey: ['glossary', bookId] })
      onApproved(`${fa(result.terms.length)} اصطلاح تأیید و ذخیره شد.`)
    },
    onError: (error) => onError(error instanceof Error ? error.message : 'تأیید ناموفق بود'),
  })

  const startEditing = () => {
    if (pristine) {
      setRows(proposal.data?.terms ?? [])
      setKept(new Set((proposal.data?.terms ?? []).map((term) => key(term.source_term))))
    }
  }

  const toggle = (sourceTerm: string) => {
    startEditing()
    setKept((previous) => {
      const next = new Set(previous)
      const identifier = key(sourceTerm)
      if (next.has(identifier)) next.delete(identifier)
      else next.add(identifier)
      return next
    })
  }

  const editTarget = (sourceTerm: string, value: string) => {
    const identifier = key(sourceTerm)
    setRows((previous) =>
      (previous ?? []).map((term) =>
        key(term.source_term) === identifier ? { ...term, target_term: value } : term,
      ),
    )
  }

  const close = () => {
    onClose()
    // Drop the local edits so reopening starts from the stored draft.
    setRows(null)
    setKept(new Set())
  }

  return (
    <div
      className="proposal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="glossary-review-title"
      onClick={(event) => {
        if (event.target === event.currentTarget) close()
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') close()
      }}
    >
      <div className="surface-elevated w-full max-w-[720px] p-6" onKeyDown={() => undefined}>
        <h2 id="glossary-review-title" className="text-[length:var(--text-h2)] font-extrabold">
          بازبینی پیشنهاد واژه‌نامه
        </h2>
        <p
          className="mt-1 mb-4 text-[length:var(--text-small)]"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          این‌ها پیشنهاد مدل هستند و هنوز واژه‌نامه نشده‌اند. هر موردی را که می‌خواهید
          نگه دارید تیک بزنید یا متنش را اصلاح کنید.
        </p>

        {proposal.isPending ? (
          <div className="skeleton" style={{ height: 200 }} />
        ) : terms.length === 0 ? (
          <p className="empty">پیشنهادی برای بازبینی وجود ندارد.</p>
        ) : (
          <div className="max-h-[52vh] overflow-auto">
            <table className="w-full border-collapse text-[length:var(--text-small)]">
              <thead>
                <tr>
                  <th scope="col" style={{ width: 44 }} className="text-start">
                    نگه‌داری
                  </th>
                  <th scope="col" className="text-start">
                    عبارت مبدأ
                  </th>
                  <th scope="col" className="text-start">
                    معادل
                  </th>
                  <th scope="col" style={{ width: 96 }} className="text-start">
                    نوع
                  </th>
                </tr>
              </thead>
              <tbody>
                {terms.map((term) => {
                  const identifier = key(term.source_term)
                  const isKept = kept.has(identifier)
                  return (
                    <tr key={identifier}>
                      <td>
                        <input
                          type="checkbox"
                          checked={isKept}
                          onChange={() => toggle(term.source_term)}
                          aria-label={`نگه‌داری ${term.source_term}`}
                        />
                      </td>
                      <td dir="ltr" className="text-start">
                        {term.source_term}
                      </td>
                      <td>
                        <input
                          type="text"
                          className="field w-full"
                          dir="auto"
                          value={term.target_term}
                          onChange={(event) => editTarget(term.source_term, event.target.value)}
                          aria-label={`معادل ${term.source_term}`}
                        />
                      </td>
                      <td>
                        <span className="badge">{KIND_FA[term.kind] ?? term.kind}</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <small
            className="text-[length:var(--text-label)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {pristine
              ? `${fa(terms.length)} مورد پیشنهاد شده است`
              : `${fa(kept.size)} از ${fa(terms.length)} مورد انتخاب شده`}
          </small>
          <div className="flex gap-2">
            <button
              type="button"
              className="btn btn-primary"
              disabled={kept.size === 0 || approve.isPending}
              onClick={() => approve.mutate()}
            >
              {approve.isPending ? 'در حال ذخیره…' : 'تأیید انتخاب‌شده‌ها'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={close}>
              انصراف
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
