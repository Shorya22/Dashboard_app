/**
 * TEMPORARY demo-only helper — DELETE BEFORE MERGING.
 *
 * Counterpart to `backend/app/core/demo_overrides.py`. The backend patches
 * the aggregate endpoints, but the Total/Active/Inactive cards on the
 * Workforce and HR Analytics pages are recomputed client-side from
 * `/roster/employees` so they can respond to the filter bar — which means
 * they bypass those overrides entirely and still show the real roster.
 *
 * This picks the API (demo) value while no filter is applied, and falls
 * back to the real client-side count as soon as the user filters, so
 * filtering still visibly works.
 *
 * Removal: delete this file and the `demoHeadcount(...)` calls in
 * `pages/workforce-page.tsx` and `pages/hr-analytics-page.tsx`.
 */
import { ALL, type FilterValues } from '@/lib/employee-filters'

export function isUnfiltered(filters: FilterValues): boolean {
  return Object.values(filters).every((v) => v === ALL || v === undefined)
}

/**
 * `apiValue` wins only while nothing is filtered; otherwise the real
 * filtered count is returned unchanged.
 */
export function demoHeadcount(
  filters: FilterValues,
  apiValue: number | undefined,
  filteredCount: number,
): number {
  if (isUnfiltered(filters) && apiValue !== undefined) return apiValue
  return filteredCount
}
