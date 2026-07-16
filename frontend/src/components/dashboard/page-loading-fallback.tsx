import { Skeleton } from '@/components/ui/skeleton'

/** Suspense fallback shown briefly while a lazy-loaded route's JS chunk is
 * being fetched. Mirrors the KPI-row + chart-grid shape most pages use so
 * the transition into the real page doesn't cause a layout jump, and
 * follows the same `Skeleton` pattern `ChartCard` already uses for
 * data-loading states elsewhere in the app. */
export function PageLoadingFallback() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-2xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Skeleton className="h-96 w-full rounded-2xl" />
        <Skeleton className="h-96 w-full rounded-2xl" />
      </div>
    </div>
  )
}
