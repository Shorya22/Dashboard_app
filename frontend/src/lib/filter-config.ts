// Filter DEFINITIONS come from the backend YAML (see
// `backend/app/services/configs/roster_metrics.yaml` and
// `booking_metrics.yaml` under the `filters:` block). Values still come
// from `/roster/filter-options` and `/utilization/filter-options` — this
// hook is definition-only (label, hierarchy, page mapping).

import { useQuery } from '@tanstack/react-query'
import { apiClient } from './api-client'

export type FilterType = 'single' | 'multi' | 'hierarchical'

export interface FilterDefinition {
  key: string
  label: string
  type: FilterType
  column_role: string | null
  derived_from_chart: string | null
  nests: string | null
  applies_to_pages: string[]
}

export interface FilterConfigResponse {
  dataset: 'roster' | 'booking'
  filters: FilterDefinition[]
}

/**
 * TanStack Query hook returning filter DEFINITIONS for one dataset.
 * Labels/hierarchy/page-mapping change only on a YAML edit + reload, so
 * this cache is effectively infinite for a session — `staleTime: Infinity`
 * so the browser never re-fetches within a session.
 */
export function useFilterConfig(dataset: 'roster' | 'booking') {
  return useQuery({
    queryKey: ['config', 'filters', dataset],
    queryFn: async () =>
      (await apiClient.get<FilterConfigResponse>(`/v1/config/filters`, { params: { dataset } })).data,
    staleTime: Infinity,
    gcTime: Infinity,
  })
}

/** Look up a single filter def by key. Throws if missing — a page should
 * never fall back to a hardcoded label string when the YAML is the source
 * of truth; a missing key is a config bug, not a runtime fallback path. */
export function getFilter(
  defs: FilterDefinition[] | undefined,
  key: string,
): FilterDefinition {
  const found = defs?.find((f) => f.key === key)
  if (!found) {
    throw new Error(
      `filter-config: no filter with key ${JSON.stringify(key)} in the config (known: ${
        defs ? defs.map((f) => f.key).join(', ') : '<not loaded>'
      })`,
    )
  }
  return found
}

/** Look up a filter def's label safely — returns `fallback` if the config
 * hasn't loaded yet, so a render before the query resolves doesn't throw.
 * Use this in JSX; use `getFilter` when a missing key is a real bug. */
export function filterLabel(
  defs: FilterDefinition[] | undefined,
  key: string,
  fallback = '',
): string {
  const found = defs?.find((f) => f.key === key)
  return found ? found.label : fallback
}
