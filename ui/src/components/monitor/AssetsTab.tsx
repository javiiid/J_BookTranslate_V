import type { Job } from '@/lib/api'
import { ASSET_FA, faBytes } from '@/lib/format'

/**
 * Assets tab.
 *
 * Links come from `asset_downloads`, not from `assets`. `assets` is the map of
 * produced file paths; only `asset_downloads` carries a URL the browser can
 * actually fetch, and a path is not a URL. Rendering the wrong one produced
 * dead links in an earlier draft of this page.
 */
export function AssetsTab({ job }: { job: Job }) {
  const downloads = job.asset_downloads ?? {}
  const entries = Object.entries(downloads)
  const assets = job.assets ?? {}

  if (entries.length === 0) {
    return <div className="surface-card empty">هنوز خروجی قابل دانلودی وجود ندارد.</div>
  }

  return (
    <div className="surface-card p-[var(--spacing-5)]">
      <div className="asset-grid">
        {entries.map(([name, href]) => {
          const label = ASSET_FA[name] ?? name
          // The raw value is a size in bytes on some entries and a path on
          // others, so it is only shown when it parses as a number.
          const raw = assets[name]
          const size = raw && /^\d+$/.test(raw) ? faBytes(Number(raw)) : ''
          return (
            <a key={name} className="asset" href={href} aria-label={`دانلود ${label}`}>
              <span className="asset-name">{label.toUpperCase()}</span>
              <span className="asset-meta">{size || name}</span>
            </a>
          )
        })}
      </div>
    </div>
  )
}
