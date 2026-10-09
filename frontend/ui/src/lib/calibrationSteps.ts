import type { Calibration } from './calibration.ts'
import { getLocale } from './locale.ts'
import { en as enDict } from '../i18n/en.ts'
import { fa as faDict } from '../i18n/fa.ts'

export type WizardStep = 0 | 1 | 2 | 3

const ROLE_FA: Record<string, string> = { narrative: 'روایت و توضیح', technical: 'متن تخصصی', dialogue: 'گفت‌وگو' }
const ROLE_EN: Record<string, string> = { narrative: 'Narrative', technical: 'Technical', dialogue: 'Dialogue' }

/** A sample's role in the active language, falling back to the raw value. */
export function roleLabelFor(role: string): string {
  const table = getLocale() === 'fa' ? ROLE_FA : ROLE_EN
  return table[role] ?? role
}

/** Kept for the two workshop views, which render the fallback themselves. */
export const roleLabel: Record<string, string> = ROLE_FA

export const WIZARD_STEPS = [
  { id: 0, label: 'لحن ترجمه', labelEn: 'Translation tone' },
  { id: 1, label: 'مدل‌ها', labelEn: 'Models' },
  { id: 2, label: 'واژه‌نامه', labelEn: 'Glossary' },
  { id: 3, label: 'بررسی و شروع', labelEn: 'Review and start' },
] as const

/** A wizard step's label in the active language. */
export function wizardStepLabel(id: number): string {
  const step = WIZARD_STEPS.find((item) => item.id === id)
  if (!step) return ''
  return getLocale() === 'fa' ? step.label : step.labelEn
}

/**
 * Server-sent tone display text, localized by stable id.
 *
 * The ids (`modern`, `literary`, …) are the backend contract in
 * `app/calibration/engine.py`; the Persian label/description beside them are
 * just the default language's words. An unknown future id falls back to the
 * server's own text rather than a blank.
 */
function toneText(id: string, suffix: '' | 'Desc', fallback: string): string {
  const table = (getLocale() === 'fa' ? faDict : enDict) as Record<string, string>
  return table[`cal.tone.${id}${suffix}`] ?? fallback
}

export function toneLabel(id: string, fallback: string): string {
  return toneText(id, '', fallback)
}

export function toneDescription(id: string, fallback: string): string {
  return toneText(id, 'Desc', fallback)
}

export interface ReviewCheck {
  key: 'approved' | 'verified' | 'sealed'
  ok: boolean
  label: string
}

/**
 * The three facts behind the seal button, in plain language.
 *
 * `canSeal` answers yes/no; this answers *why not*, so a disabled
 * button is an explanation rather than a dead end.
 */
export function reviewChecks(session: Calibration): ReviewCheck[] {
  const total = session.samples.length
  const approved = session.samples.filter((s) => s.approved).length
  const allVerified = total > 0 && session.samples.every((s) => s.final_verified)
  const sealed = !session.busy && !session.job_id && total > 0 && session.samples.every((s) => s.approved && s.final_verified)
  const en = getLocale() !== 'fa'
  return [
    {
      key: 'approved',
      ok: total > 0 && approved === total,
      label: total === 0
        ? en ? 'No samples yet' : 'هنوز نمونه‌ای نیست'
        : en ? `${approved} of ${total} samples approved` : `${approved} از ${total} نمونه تأیید شده`,
    },
    {
      key: 'verified',
      ok: allVerified,
      label: allVerified
        ? en ? 'All verified against the final model' : 'همه با مدل نهایی تأیید شدند'
        : en ? 'Some samples are not verified against the final model' : 'برخی نمونه‌ها با مدل نهایی تأیید نشده‌اند',
    },
    {
      key: 'sealed',
      ok: sealed,
      label: sealed
        ? en ? 'Ready to lock the profile' : 'آمادهٔ قفل پروفایل'
        : session.job_id
          ? en ? 'Profile locked and translating' : 'پروفایل قفل شده و وارد ترجمه شده است'
          : session.busy
            ? en ? 'An operation is running; check when it finishes' : 'عملیاتی در حال اجراست؛ پس از اتمام بررسی کنید'
            : en ? 'Not ready to lock yet' : 'هنوز آمادهٔ قفل نیست',
    },
  ]
}

/**
 * Every wizard step is viewable; only the seal action is gated.
 *
 * Steps 0-2 are always enterable so a newcomer can look ahead.
 * Step 3 (review) is also enterable when samples are unverified --
 * the seal button inside it explains what is missing.
 * The function exists so navigation rules stay testable in one place.
 */
export function canEnterStep(session: Calibration | null | undefined, step: WizardStep): boolean {
  if (!session) return step === 0
  if (step < 0 || step > 3) return false
  return true
}

export function nextIncompleteStep(session: Calibration): WizardStep {
  if (session.samples.length === 0) return 0
  if (session.samples.some((s) => !s.result)) return 0
  if (session.samples.some((s) => !s.final_verified)) return 1
  if (session.samples.some((s) => !s.approved)) return 2
  return 3
}
