import * as React from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search as SearchIcon, RotateCcw } from 'lucide-react'
import { Card } from '@tremor/react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useUtilizationFilterOptions,
  useUtilizationHoldingsProjects,
  useUtilizationByRegionMarket,
} from '@/lib/utilization-api'
import { HierarchicalMultiSelect, type HierarchicalItem } from '@/components/dashboard/hierarchical-multi-select'
import { marketDisplayLabel } from '@/lib/chart-colors'

type FilterKey = 'week' | 'region' | 'department' | 'entity' | 'holding' | 'hours_type'

interface FilterField {
  key: FilterKey
  label: string
}

const FIELDS: FilterField[] = [
  { key: 'week', label: 'Week' },
  { key: 'region', label: 'Region (EC), Market (EC)' },
  { key: 'department', label: 'Department' },
  { key: 'entity', label: 'Entity' },
  { key: 'holding', label: 'Holding, Project' },
  { key: 'hours_type', label: 'Hours Type' },
]

const MONTH_FMT = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' })
const DAY_FMT = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })

// Holding->Project child values are encoded as "<holding>::<project>" so
// each project row has a unique key (the same project name can recur under
// different holdings). This helper recovers the real "holding" filter
// value the backend understands from either a plain holding value or a
// composite holding::project child value.
function holdingFromValue(value: string): string {
  const idx = value.indexOf('::')
  return idx === -1 ? value : value.slice(0, idx)
}

// Region->Market child values are similarly encoded as "<region>::<market>"
// (composite key, since the same market string could recur under different
// regions in principle). Splits a selected region-field value into its raw
// `region` and/or `market` filter contribution: a plain top-level selection
// contributes only `region`; a market child contributes only `market` (the
// market value alone already narrows to the right rows — the backend ANDs
// region/market together, so we don't need to also carry the parent region
// unless it was independently selected).
function splitRegionMarketValue(value: string): { region?: string; market?: string } {
  const idx = value.indexOf('::')
  if (idx === -1) return { region: value }
  return { market: value.slice(idx + 2) }
}

/** Groups ISO week-start dates ("2026-05-04") into month parents ("May
 * 2026") with each date as a labelled child ("04 May 2026"). */
function weeksToHierarchy(weeks: string[]): HierarchicalItem[] {
  return weeks.map((week) => {
    const d = new Date(`${week}T00:00:00`)
    return { value: week, label: DAY_FMT.format(d), parent: MONTH_FMT.format(d) }
  })
}

function flatHierarchy(values: string[]): HierarchicalItem[] {
  return values.map((v) => ({ value: v, label: v }))
}

export function UtilizationSearchPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const filterOptions = useUtilizationFilterOptions()
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
    FIELDS.forEach((field) => {
      initial[field.key] = searchParams.getAll(field.key)
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
        const regions = new Set<string>()
        const markets = new Set<string>()
        arr.forEach((v) => {
          const { region, market } = splitRegionMarketValue(v)
          if (region) regions.add(region)
          if (market) markets.add(market)
        })
        regions.forEach((r) => params.append('region', r))
        markets.forEach((m) => params.append('market', m))
      } else {
        arr.forEach((v) => params.append(k, v))
      }
    })
    navigate(`/utilization/results?${params.toString()}`)
  }

  const handleReset = () => {
    const cleared = {} as Record<FilterKey, string[]>
    FIELDS.forEach((f) => (cleared[f.key] = []))
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
      week: weeksToHierarchy(data.weeks),
      region: regionHierarchy,
      department: flatHierarchy(data.departments),
      entity: flatHierarchy(data.entities),
      holding: holdingHierarchy,
      hours_type: flatHierarchy(data.hours_types),
    }
  }, [filterOptions.data, holdingsProjects.data, byRegionMarket.data])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Search Utilization</h1>
        <p className="text-sm text-muted-foreground">
          Filter time-booking records by week, region, department, entity, holding, or hours type
        </p>
      </div>

      <Card className="rounded-2xl border-border bg-card p-6 shadow-card">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FIELDS.map((field) => (
              <div key={field.key} className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">{field.label}</label>
                {filterOptions.isLoading ? (
                  <Skeleton className="h-10 w-full rounded-lg" />
                ) : (
                  <HierarchicalMultiSelect
                    items={hierarchies[field.key]}
                    selected={values[field.key]}
                    onChange={(next) => setField(field.key, next)}
                    searchable={field.key === 'holding'}
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
