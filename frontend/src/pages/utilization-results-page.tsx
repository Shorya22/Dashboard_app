import * as React from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Clock, Briefcase, Building2, FolderKanban, BarChart2 } from 'lucide-react'
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { FilterSelect } from '@/components/dashboard/filter-select'
import { FiltersPanel } from '@/components/dashboard/filters-panel'
import { marketDisplayLabel } from '@/lib/chart-colors'
import {
  useUtilizationRecords,
  useUtilizationFilterOptions,
  type UtilizationRecord,
} from '@/lib/utilization-api'

/** Formats a KPI number, falling back to a dash instead of "NaN"/"undefined"
 * when the backend returns a null/undefined value (e.g. Internal Hours can
 * legitimately be absent for a filtered result set with zero internal
 * hours booked). */
function formatHours(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '—'
}

const PAGE_SIZE = 25

const columns: ColumnDef<UtilizationRecord>[] = [
  { accessorKey: 'week_start', header: 'Week Start' },
  { accessorKey: 'date', header: 'Date' },
  {
    accessorKey: 'employee',
    header: 'Employee',
    cell: ({ getValue }) => {
      const name = getValue<string>()
      return (
        <Link
          to={`/utilization/employees/${encodeURIComponent(name)}`}
          className="font-medium text-primary hover:underline"
        >
          {name}
        </Link>
      )
    },
  },
  { accessorKey: 'project', header: 'Project' },
  {
    accessorKey: 'holding',
    header: 'Holding',
    cell: ({ getValue }) => {
      const holding = getValue<string>()
      return (
        <Link
          to={`/utilization/projects/${encodeURIComponent(holding)}`}
          className="font-medium text-primary hover:underline"
        >
          {holding}
        </Link>
      )
    },
  },
  {
    accessorKey: 'department',
    header: 'Department',
    cell: ({ getValue }) => getValue<string>() ?? '—',
  },
  {
    accessorKey: 'team',
    header: 'Team (EC)',
    cell: ({ getValue }) => getValue<string>() ?? '—',
  },
  {
    accessorKey: 'region',
    header: 'Region',
    cell: ({ getValue }) => getValue<string>() ?? '—',
  },
  { accessorKey: 'hours_type', header: 'Hours Type' },
  {
    accessorKey: 'hours',
    header: 'Hours',
    cell: ({ getValue }) => formatHours(getValue<number>()),
  },
]

export function UtilizationResultsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = parseInt(searchParams.get('page') ?? '0', 10)

  // Each filter field may carry multiple values in the URL (repeated
  // params, e.g. `?region=EMEA&region=AMER`, set by the Search page's
  // multi-select). `getAll` collects all of them; an empty array means "no
  // filter on this field" and is normalized to `undefined` so it's dropped
  // from the outgoing request instead of sent as `[]`.
  const getAllOrUndefined = (key: string) => {
    const all = searchParams.getAll(key)
    return all.length > 0 ? all : undefined
  }

  const filters = React.useMemo(
    () => ({
      week: getAllOrUndefined('week'),
      region: getAllOrUndefined('region'),
      market: getAllOrUndefined('market'),
      department: getAllOrUndefined('department'),
      entity: getAllOrUndefined('entity'),
      holding: getAllOrUndefined('holding'),
      hours_type: getAllOrUndefined('hours_type'),
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searchParams, page],
  )

  const records = useUtilizationRecords(filters)
  const filterOptions = useUtilizationFilterOptions()

  // The sidebar's per-field dropdowns are single-select (unlike the
  // Search page's multi-select). Picking a value here replaces ALL
  // previously selected values for that field with the single new one.
  const setFilter = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(searchParams)
    next.delete(key)
    if (value) next.set(key, value)
    next.delete('page')
    setSearchParams(next)
  }

  const table = useReactTable({
    data: records.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  const total = records.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const goToPage = (p: number) => {
    const next = new URLSearchParams(searchParams)
    next.set('page', String(p))
    setSearchParams(next)
  }

  const activeFilters = Object.entries({
    Week: filters.week,
    Region: filters.region,
    Market: filters.market,
    Department: filters.department,
    Entity: filters.entity,
    Holding: filters.holding,
    'Hours Type': filters.hours_type,
  })
    .filter(([, v]) => v && v.length > 0)
    .map(([k, v]) => {
      const values = v as string[]
      const display = k === 'Market' ? values.map(marketDisplayLabel) : values
      return [k, display.join(', ')] as const
    })

  // Preserve the active filters when going back to the search page.
  const backToSearchParams = new URLSearchParams(searchParams)
  backToSearchParams.delete('page')

  const searchHref = `/utilization/search${backToSearchParams.toString() ? `?${backToSearchParams.toString()}` : ''}`

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-6">
      <div className="flex items-center gap-3">
        <Link
          to={searchHref}
          aria-label="Back to search"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border bg-card text-foreground shadow-card transition-colors hover:bg-muted/50"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Utilization Results</h1>
          <p className="text-sm text-muted-foreground">
            {activeFilters.length > 0
              ? `Filtered by ${activeFilters.map(([k, v]) => `${k}: ${v}`).join(', ')}`
              : 'Showing all records'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard
          label="Total Hours"
          value={formatHours(records.data?.summary.total_hours)}
          loading={records.isLoading}
          icon={Clock}
          iconTone="orange"
        />
        <KpiCard
          label="Client Hours"
          value={formatHours(records.data?.summary.client_hours)}
          loading={records.isLoading}
          icon={Briefcase}
          iconTone="orange"
        />
        <KpiCard
          label="Internal Hours"
          value={formatHours(records.data?.summary.internal_hours)}
          loading={records.isLoading}
          icon={Building2}
          iconTone="blue"
        />
        <KpiCard
          label="Total Projects"
          value={records.data?.summary.total_projects ?? '—'}
          loading={records.isLoading}
          icon={FolderKanban}
          iconTone="blue"
        />
        <KpiCard
          label="Average Hours"
          value={
            typeof records.data?.summary.average_hours === 'number' &&
            Number.isFinite(records.data.summary.average_hours)
              ? records.data.summary.average_hours.toFixed(2)
              : '—'
          }
          loading={records.isLoading}
          icon={BarChart2}
          iconTone="blue"
        />
      </div>

      <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-muted/50">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th key={header.id} className="whitespace-nowrap px-3 py-2 text-left font-medium">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {records.isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-t border-border">
                  {columns.map((_, j) => (
                    <td key={j} className="px-3 py-2">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  ))}
                </tr>
              ))
            ) : records.isError ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                  Couldn't load results. Try refreshing.
                </td>
              </tr>
            ) : table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                  No records match these filters.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-t border-border hover:bg-muted/30">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="whitespace-nowrap px-3 py-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext()) ?? '—'}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
          {!records.isLoading && !records.isError && table.getRowModel().rows.length > 0 && (
            <tfoot>
              <tr className="border-t-2 border-orange-600 bg-orange-500 font-semibold text-white">
                <td className="px-3 py-2" colSpan={columns.length - 1}>
                  Total
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  {records.data?.summary.total_hours.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '—'}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {!records.isLoading && total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {page + 1} of {totalPages} · {total.toLocaleString()} records
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => goToPage(page - 1)}>
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page + 1 >= totalPages}
              onClick={() => goToPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      <div className="pt-2">
        <Button asChild variant="outline" size="sm">
          <Link to={searchHref} className="inline-flex items-center gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            Back to Search
          </Link>
        </Button>
      </div>
      </div>

      <FiltersPanel>
        <FilterSelect
          label="Week"
          value={filters.week?.[0]}
          options={filterOptions.data?.weeks ?? []}
          onChange={(v) => setFilter('week', v)}
        />
        <FilterSelect
          label="Region"
          value={filters.region?.[0]}
          options={filterOptions.data?.regions ?? []}
          onChange={(v) => setFilter('region', v)}
        />
        <FilterSelect
          label="Market"
          value={filters.market?.[0]}
          options={filterOptions.data?.markets ?? []}
          getOptionLabel={marketDisplayLabel}
          onChange={(v) => setFilter('market', v)}
        />
        <FilterSelect
          label="Department"
          value={filters.department?.[0]}
          options={filterOptions.data?.departments ?? []}
          onChange={(v) => setFilter('department', v)}
        />
        <FilterSelect
          label="Entity"
          value={filters.entity?.[0]}
          options={filterOptions.data?.entities ?? []}
          onChange={(v) => setFilter('entity', v)}
        />
        <FilterSelect
          label="Holding"
          value={filters.holding?.[0]}
          options={filterOptions.data?.holdings ?? []}
          onChange={(v) => setFilter('holding', v)}
        />
        <FilterSelect
          label="Hours Type"
          value={filters.hours_type?.[0]}
          options={filterOptions.data?.hours_types ?? []}
          onChange={(v) => setFilter('hours_type', v)}
        />
      </FiltersPanel>
    </div>
  )
}
