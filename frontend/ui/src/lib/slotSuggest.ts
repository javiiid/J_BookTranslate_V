import type { CalibrationTerm } from './calibration.ts'

/**
 * Normalize the same way the backend matcher does
 * (`app/glossary/service.py::matching_terms`): NFKC + casefold.
 * No stemming: a Persian stemmer that guesses wrong suggests wrong,
 * and silence is better than noise.
 */
export function normalizeTerm(value: string): string {
  return (value ?? '').normalize('NFKC').toLowerCase()
}

/**
 * Glossary terms worth suggesting for one source slot.
 *
 * Only `approved` terms with both sides filled, whose source term
 * occurs in the slot text. Longer source terms first (more specific),
 * capped so a slot never becomes a wall of chips.
 */
export function slotSuggestions(
  sourceText: string,
  glossary: CalibrationTerm[],
  limit = 3,
): CalibrationTerm[] {
  const haystack = normalizeTerm(sourceText)
  if (!haystack) return []
  const seen = new Set<string>()
  const matched = (glossary ?? []).filter((term) => {
    if (!term.approved) return false
    const source = normalizeTerm(term.source_term)
    const target = (term.target_term ?? '').trim()
    if (!source || !target) return false
    if (seen.has(source)) return false
    if (!haystack.includes(source)) return false
    seen.add(source)
    return true
  })
  matched.sort((a, b) => normalizeTerm(b.source_term).length - normalizeTerm(a.source_term).length)
  return matched.slice(0, Math.max(0, limit))
}
