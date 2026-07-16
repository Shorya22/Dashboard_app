import * as React from 'react'

/**
 * Persistent status bar pinned to the bottom of the app shell, visible on
 * every dashboard page (see AppLayout). Power BI-style footer convention:
 * "All data as of <timestamp>".
 *
 * NOTE: the backend does not currently expose a real "data as of" / last
 * refreshed timestamp on any roster or booking endpoint (checked
 * lib/roster-api.ts — RosterSummary, RosterBreakdowns, BookingSummary, etc.
 * carry no such field). Rather than fabricate a fake data-freshness claim,
 * this shows the real moment the browser last loaded/rendered the
 * dashboard, worded to not imply it reflects source-data recency. If a
 * real "data as of" field gets added to a backend response (e.g. an
 * Excel file mtime or a load-cache timestamp), wire it in here instead of
 * `loadedAt` and restore the "All data as of ..." phrasing.
 */
export function StatusFooter() {
  const [loadedAt] = React.useState(() => new Date())

  const formatted = loadedAt.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })

  return (
    <footer className="shrink-0 px-4 py-2 text-center text-[11px] text-muted-foreground sm:px-6">
      <span className="truncate">
        All data as of {formatted} <span className="mx-1.5 text-border">|</span> Browser load time, not a live feed
      </span>
    </footer>
  )
}
