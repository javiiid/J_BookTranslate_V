export type DiffKind = 'same' | 'add' | 'del'

export interface DiffPart {
  text: string
  kind: DiffKind
}

/**
 * Word-level diff of a model draft against the reader's edit.
 *
 * Character-level diffs are unreadable on joined Persian script;
 * word level is what "3 words added, 1 removed" means. The unit is a
 * word *with its trailing whitespace*, compared byte-exactly: a
 * `same` unit is therefore identical on both sides, which is what
 * makes both reconstructions exact. Whitespace is never painted on
 * its own -- it always rides with its word.
 */
export function wordDiff(base: string, edited: string): DiffPart[] {
  const parsedBase = parse(base ?? '')
  const parsedEdited = parse(edited ?? '')

  const parts: DiffPart[] = []
  const push = (text: string, kind: DiffKind) => {
    if (!text) return
    const last = parts[parts.length - 1]
    if (last && last.kind === kind) last.text += text
    else parts.push({ text, kind })
  }

  if (parsedBase.lead === parsedEdited.lead) {
    push(parsedBase.lead, 'same')
  } else {
    push(parsedBase.lead, 'del')
    push(parsedEdited.lead, 'add')
  }

  const baseUnits = parsedBase.units
  const editedUnits = parsedEdited.units
  if (baseUnits.length === 0 && editedUnits.length === 0) {
    return parts.filter((p) => p.text !== '')
  }

  // Slots are paragraphs (tens of units). Cap pathological inputs:
  // beyond this a whole-block verdict is more readable anyway.
  const CAP = 600
  if (baseUnits.length > CAP || editedUnits.length > CAP) {
    if ((base ?? '') === (edited ?? '')) {
      push(base ?? '', 'same')
      return parts.filter((p) => p.text !== '')
    }
    return [
      ...(base ? [{ text: base, kind: 'del' as DiffKind }] : []),
      ...(edited ? [{ text: edited, kind: 'add' as DiffKind }] : []),
    ]
  }

  const ops = lcsOps(baseUnits, editedUnits)
  let bi = 0
  let ei = 0
  for (const op of ops) {
    if (op === 'same') {
      push(editedUnits[ei] as string, 'same')
      bi++
      ei++
    } else if (op === 'del') {
      push(baseUnits[bi] as string, 'del')
      bi++
    } else {
      push(editedUnits[ei] as string, 'add')
      ei++
    }
  }
  return parts.filter((p) => p.text !== '')
}

interface Parsed {
  lead: string
  units: string[]
}

/** Leading whitespace plus word-with-trailing-space units. */
function parse(value: string): Parsed {
  const leadMatch = /^\s*/.exec(value)
  const lead = leadMatch ? leadMatch[0] : ''
  const rest = value.slice(lead.length)
  const units: string[] = []
  const re = /(\S+\s*)/g
  let match: RegExpExecArray | null
  while ((match = re.exec(rest)) !== null) {
    units.push(match[1] ?? '')
  }
  return { lead, units }
}

/** LCS backtrack as an op stream over the two word lists. */
function lcsOps(a: string[], b: string[]): DiffKind[] {
  const n = a.length
  const m = b.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let x = n - 1; x >= 0; x--) {
    for (let y = m - 1; y >= 0; y--) {
      dp[x]![y] = a[x] === b[y] ? (dp[x + 1]![y + 1] ?? 0) + 1 : Math.max(dp[x + 1]![y] ?? 0, dp[x]![y + 1] ?? 0)
    }
  }
  const ops: DiffKind[] = []
  let x = 0
  let y = 0
  while (x < n && y < m) {
    if (a[x] === b[y]) {
      ops.push('same')
      x++
      y++
    } else if ((dp[x + 1]?.[y] ?? 0) >= (dp[x]?.[y + 1] ?? 0)) {
      ops.push('del')
      x++
    } else {
      ops.push('add')
      y++
    }
  }
  while (x < n) {
    ops.push('del')
    x++
  }
  while (y < m) {
    ops.push('add')
    y++
  }
  return ops
}

/** Word counts behind a diff, for the screen-reader summary. */
export function diffSummary(parts: DiffPart[]): { added: number; removed: number } {
  let added = 0
  let removed = 0
  for (const part of parts) {
    const count = part.text.split(/\s+/).filter(Boolean).length
    if (part.kind === 'add') added += count
    else if (part.kind === 'del') removed += count
  }
  return { added, removed }
}
