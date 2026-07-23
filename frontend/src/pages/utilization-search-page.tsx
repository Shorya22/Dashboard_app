import * as React from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search as SearchIcon, RotateCcw } from 'lucide-react'
import { Card } from '@tremor/react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  splitRegionMarketSelection,
  useUtilizationFilterOptions,
  useUtilizationHoldingsProjects,
  useUtilizationByRegionMarket,
  weekHierarchyToItems,
} from '@/lib/utilization-api'
import { useFilterConfig, filterLabel } from '@/lib/filter-config'
import { HierarchicalMultiSelect, type HierarchicalItem } from '@/components/dashboard/hierarchical-multi-select'
import { marketDisplayLabel } from '@/lib/chart-colors'

type FilterKey = 'week' | 'region' | 'department' | 'entity' | 'holding' | 'hours_type'

// Field ORDER lives here (a display concern the config doesn't own);
// LABELS come from the booking YAML via `useFilterConfig('booking')`.
const FIELD_KEYS: FilterKey[] = ['week', 'region', 'department', 'entity', 'holding', 'hours_type']

// Holding->Project child values are encoded as "<holding>::<project>" so
// each project row has a unique key (the same project name can recur under
// different holdings). This helper recovers the real "holding" filter
// value the backend understands from either a plain holding value or a
// composite holding::project child value.
function holdingFromValue(value: string): string {
  const idx = value.indexOf('::')
  return idx === -1 ? value : value.slice(0, idx)
}

function flatHierarchy(values: string[]): HierarchicalItem[] {
  return values.map((v) => ({ value: v, label: v }))
}

export function UtilizationSearchPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const filterOptions = useUtilizationFilterOptions()
  const filterConfig = useFilterConfig('booking')
  const holdingsProjects = useUtilizationHoldingsProjects()
  // Region -> Market grouping isn't given directly by `filter-options`
  // (that only returns a flat `markets` list, no per-region breakdown), so
  // it's derived from `/utilization/by-region-market`'s (region, market)
  // pairs — the only endpoint that actually associates the two.
  const byRegionMarket = useUtilizationByRegionMarket()

  // Pre-fill from URL query params so filters selected on this page survive
  // a round trip through the Results page's "Back to Search" link (which
  // encodes the active filters as query params). Each field now holds an
  // array of selected values (multi-select) instead of a single string.
  const [values, setValues] = React.useState<Record<FilterKey, string[]>>(() => {
    const initial = {} as Record<FilterKey, string[]>
    FIELD_KEYS.forEach((key) => {
      initial[key] = searchParams.getAll(key)
    })
    return initial
  })

  // Raw `market` values from the URL (e.g. from "Back to Search") can't be
  // turned into the region field's "region::market" composite selection
  // until `/utilization/by-region-market` has loaded (that's what supplies
  // the region each market belongs to). Resolve them once that data lands.
  const pendingMarketsRef = React.useRef<string[]>(searchParams.getAll('market'))
  React.useEffect(() => {
    if (pendingMarketsRef.current.length === 0 || !byRegionMarket.data) return
    const pending = new Set(pendingMarketsRef.current)
    const resolved = new Set<string>()
    byRegionMarket.data.items.forEach(({ region, market }) => {
      if (pending.has(market)) resolved.add(`${region}::${market}`)
    })
    if (resolved.size > 0) {
      setValues((prev) => ({
        ...prev,
        region: Array.from(new Set([...prev.region, ...resolved])),
      }))
    }
    pendingMarketsRef.current = []
  }, [byRegionMarket.data])

  const setField = (key: FilterKey, next: string[]) => {
    setValues((prev) => ({ ...prev, [key]: next }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const params = new URLSearchParams()
    // Submit every selected value per field as a repeated query param
    // (`?region=EMEA&region=AMER`), matching what
    // `GET /api/v1/utilization/records` expects (OR within a field, AND
    // across fields — see backend/app/api/utilization.py). There is still
    // no `project` filter param, only `holding`, so composite
    // "holding::project" child selections are collapsed to their raw
    // holding value (project is display/grouping only on this page).
    Object.entries(values).forEach(([k, arr]) => {
      if (arr.length === 0) return
      if (k === 'holding') {
        const holdings = new Set(arr.map(holdingFromValue))
        holdings.forEach((h) => params.append('holding', h))
      } else if (k === 'region') {
        const { region, market } = splitRegionMarketSelection(arr)
        region?.forEach((r) => params.append('region', r))
        market?.forEach((m) => params.append('market', m))
      } else {
        arr.forEach((v) => params.append(k, v))
      }
    })
    navigate(`/utilization/results?${params.toString()}`)
  }

  const handleReset = () => {
    const cleared = {} as Record<FilterKey, string[]>
    FIELD_KEYS.forEach((k) => (cleared[k] = []))
    setValues(cleared)
  }

  const hierarchies: Record<FilterKey, HierarchicalItem[]> = React.useMemo(() => {
    const data = filterOptions.data
    if (!data) {
      return { week: [], region: [], department: [], entity: [], holding: [], hours_type: [] }
    }

    // Region -> Market hierarchy, derived from /utilization/by-region-market
    // (region, market) pairs. Market values are shown to the user with the
    // confirmed display alias (BN -> BENO, Technology -> AMER; DACH/UKI
    // unchanged) but the underlying `value` stays the raw market string so
    // submission still sends the API the value it understands.
    const regionHierarchy: HierarchicalItem[] = data.regions.map((r) => ({ value: r, label: r }))
    if (byRegionMarket.data) {
      const seen = new Set<string>()
      byRegionMarket.data.items.forEach(({ region, market }) => {
        const key = `${region}::${market}`
        if (seen.has(key)) return
        seen.add(key)
        regionHierarchy.push({ value: key, label: marketDisplayLabel(market), parent: region })
      })
    }

    // Holding -> Project hierarchy from the dedicated
    // GET /utilization/holdings-projects endpoint (43 holdings), instead of
    // paginating through every booking record client-side.
    const holdingHierarchy: HierarchicalItem[] = []
    if (holdingsProjects.data) {
      holdingsProjects.data.items.forEach(({ holding, projects }) => {
        if (projects.length === 0) {
          holdingHierarchy.push({ value: holding, label: holding })
          return
        }
        projects.forEach((project) => {
          holdingHierarchy.push({ value: `${holding}::${project}`, label: project, parent: holding })
        })
      })
    }

    return {
      // Uses the canonical Year > Month > Week tree helper from
      // utilization-api.ts (Phase 1) — the same one Utilization Home /
      // Results use, so labels can't drift between pages.
      week: weekHierarchyToItems(data.week_hierarchy),
      region: regionHierarchy,
      department: flatHierarchy(data.departments),
      entity: flatHierarchy(data.entities),
      holding: holdingHierarchy,
      hours_type: flatHierarchy(data.hours_types),
    }
  }, [filterOptions.data, holdingsProjects.data, byRegionMarket.data])

  return (
    <div className="space-y-5">
      <Card className="rounded-2xl border-border bg-card p-6 shadow-card">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FIELD_KEYS.map((key) => (
              <div key={key} className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  {filterLabel(filterConfig.data?.filters, key, key)}
                </label>
                {filterOptions.isLoading ? (
                  <Skeleton className="h-10 w-full rounded-lg" />
                ) : (
                  <HierarchicalMultiSelect
                    items={hierarchies[key]}
                    selected={values[key]}
                    onChange={(next) => setField(key, next)}
                    searchable={key === 'holding'}
                  />
                )}
              </div>
            ))}
          </div>

          {filterOptions.isError && (
            <p className="text-sm text-destructive">
              Couldn't load filter options. Try refreshing the page.
            </p>
          )}

          <div className="flex items-center gap-3 pt-2">
            <Button type="submit" className="gap-2">
              <SearchIcon className="h-4 w-4" />
              Search
            </Button>
            <Button type="button" variant="outline" onClick={handleReset} className="gap-2">
              <RotateCcw className="h-4 w-4" />
              Reset
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
