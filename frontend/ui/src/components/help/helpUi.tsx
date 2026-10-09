/**
 * Query highlighting for the help center, as React nodes.
 *
 * `<mark>` around matched substrings of the original text -- never the
 * query injected into raw HTML, so nothing the user typed can become
 * markup.
 */
export function Highlight({ text, query }: { text: string; query: string }) {
  const tokens = query
    .split(/\s+/)
    .map((part) => part.trim())
    .filter((part) => part.length > 1)
  if (tokens.length === 0) return <>{text}</>
  const lower = text.toLowerCase()
  const ranges: Array<[number, number]> = []
  for (const token of tokens) {
    const needle = token.toLowerCase()
    let from = 0
    for (;;) {
      const found = lower.indexOf(needle, from)
      if (found === -1 || ranges.length >= 32) break
      ranges.push([found, found + needle.length])
      from = found + needle.length
    }
    if (ranges.length >= 32) break
  }
  if (ranges.length === 0) return <>{text}</>
  ranges.sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const merged: Array<[number, number]> = []
  for (const range of ranges) {
    const last = merged[merged.length - 1]
    if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1])
    else merged.push([range[0], range[1]])
  }
  const parts: React.ReactNode[] = []
  let cursor = 0
  merged.forEach(([start, end], index) => {
    if (start > cursor) parts.push(text.slice(cursor, start))
    parts.push(<mark key={index}>{text.slice(start, end)}</mark>)
    cursor = end
  })
  if (cursor < text.length) parts.push(text.slice(cursor))
  return <>{parts}</>
}
