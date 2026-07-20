import * as React from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { ArrowLeft, ArrowUpDown, ChevronLeft, ChevronRight, Clock, Briefcase, Building2, FolderX, Users, Search } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { FilterSelect } from '@/components/dashboard/filter-select'
import { FiltersPanel } from '@/components/dashboard/filters-panel'
import { Input } from '@/components/ui/input'
import { withTruncatedLabels } from '@/lib/chart-labels'
import { HOURS_TYPE_COLORS } from '@/lib/chart-colors'
import { Skeleton } from '@/components/ui/skeleton'
import { TableScrollContainer } from '@/components/dashboard/table-scroll-container'
import {
  useProjectUtilization,
  useUtilizationRecordsAll,
  type ProjectDetailRow,
} from '@/lib/utilization-api'

// Hoisted to module scope so its array reference is stable across renders,
// matching CustomBarChart's React.memo (values are constant, not derived
// from any state) — reused by both charts below.
const HOURS_TYPE_SERIES = [
  { category: 'Client Hours', color: HOURS_TYPE_COLORS['Client Hours'] },
  { category: 'Internal Hours', color: HOURS_TYPE_COLORS['Internal Hours'] },
]

const fmtHours = (v: number) =>
  v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

interface HoldingSummaryRow {
  holding: string
  totalEmployees: number
  totalHours: number
}

const PAGE_SIZES = [25, 50, 100]

/** Landing state for `/utilization/projects` (no `:holding` param) —
 * reached from the sidebar rather than a drill-through click. Shows one
 * row per holding/project with aggregated totals (client-side groupby
 * over the raw booking records), a name search box, and sortable
 * columns. Clicking a row navigates to the existing
 * `/utilization/projects/:holding` detail route. */
function ProjectPickerPage() {
  
  const recordsQuery = useUtilizationRecordsAll({})
  const [search, setSearch] = React.useState('')
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [pageSize, setPageSize] = React.useState(25)
  const [pageIndex, setPageIndex] = React.useState(0)

  const summaryRows = React.useMemo<HoldingSummaryRow[]>(() => {
    const totals = new Map<string, { totalHours: number; employees: Set<string> }>()
    for (const r of recordsQuery.data?.items ?? []) {
      // One booking row is a known, unfixed data-quality issue (see
      // data-model skill) with every field but Project URL blank —
      // `holding` is null there, which would otherwise crash the sort
      // below (`.localeCompare` on null).
      if (!r.holding) continue
      const row = totals.get(r.holding) ?? { totalHours: 0, employees: new Set<string>() }
      row.totalHours += r.hours
      row.employees.add(r.employee)
      totals.set(r.holding, row)
    }
    return Array.from(totals, ([holding, v]) => ({
      holding,
      totalEmployees: v.employees.size,
      totalHours: v.totalHours,
    })).sort((a, b) => a.holding.localeCompare(b.holding))
  }, [recordsQuery.data])

  const filteredRows = React.useMemo(() => {
    if (!search.trim()) return summaryRows
    const q = search.trim().toLowerCase()
    return summaryRows.filter((r) => r.holding.toLowerCase().includes(q))
  }, [summaryRows, search])

  const columns = React.useMemo<ColumnDef<HoldingSummaryRow>[]>(
    () => [
      {
        id: 'serial',
        header: '#',
        enableSorting: false,
        // `row.index` is the row's position within the full sorted (but
        // un-paginated) row model fed to the table, so it already reflects
        // the correct overall rank — no page-offset math needed here.
        cell: ({ row }) => row.index + 1,
      },
      {
        accessorKey: 'holding',
        header: 'Holding / Project',
        cell: ({ getValue, row }) => (
          <Link
            to={`/utilization/projects/${encodeURIComponent(row.original.holding)}`}
            className="font-medium text-primary hover:underline"
          >
            {getValue<string>()}
          </Link>
        ),
      },
      { accessorKey: 'totalEmployees', header: 'Total Employees' },
      {
        accessorKey: 'totalHours',
        header: 'Total Hours',
        cell: ({ getValue }) => fmtHours(getValue<number>()),
      },
      {
        id: 'view',
        header: '',
        cell: ({ row }) => (
          <Link
            to={`/utilization/projects/${encodeURIComponent(row.original.holding)}`}
            className="text-sm text-primary hover:underline"
          >
            View →
          </Link>
        ),
      },
    ],
    [],
  )

  const table = useReactTable({
    data: filteredRows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  // Pagination footer recomputes from the FILTERED count, matching the
  // Employee Directory table's pattern — narrowing the search resets to
  // page 1 and "Page X of Y" reflects the filtered set, not the full list.
  const total = filteredRows.length
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const clampedPageIndex = Math.min(pageIndex, pageCount - 1)
  const sortedRows = table.getSortedRowModel().rows
  const pageRows = sortedRows.slice(clampedPageIndex * pageSize, clampedPageIndex * pageSize + pageSize)

  React.useEffect(() => {
    setPageIndex(0)
  }, [search, pageSize])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search projects…"
            className="pl-8"
          />
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="project-page-size" className="text-muted-foreground">
            Rows per page
          </label>
          <select
            id="project-page-size"
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
            className="rounded-md border border-border bg-background px-2 py-1"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
      </div>

      <TableScrollContainer>
        <table className="w-full min-w-[720px] text-sm">
          <thead className="sticky top-0 z-10 bg-muted">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={header.column.getCanSort() ? header.column.getToggleSortingHandler() : undefined}
                    className="cursor-pointer select-none whitespace-nowrap px-3 py-2 text-left font-medium"
                  >
                    <span className="inline-flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.columnDef.header && <ArrowUpDown className="h-3 w-3 text-muted-foreground" />}
                      {header.column.getIsSorted() === 'asc' && ' ▲'}
                      {header.column.getIsSorted() === 'desc' && ' ▼'}
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {recordsQuery.isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-t border-border">
                  {columns.map((_, j) => (
                    <td key={j} className="px-3 py-2">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  ))}
                </tr>
              ))
            ) : recordsQuery.isError ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                  Couldn't load projects. Try refreshing.
                </td>
              </tr>
            ) : pageRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                  {summaryRows.length === 0 ? 'No projects available.' : `No matches for "${search}".`}
                </td>
              </tr>
            ) : (
              pageRows.map((row) => (
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
        </table>
      </TableScrollContainer>

      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-muted-foreground">
          Page {clampedPageIndex + 1} of {pageCount} {recordsQuery.isFetching && '· updating…'}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={clampedPageIndex === 0}
            onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" /> Prev
          </button>
          <button
            type="button"
            disabled={clampedPageIndex + 1 >= pageCount}
            onClick={() => setPageIndex((p) => p + 1)}
            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
          >
            Next <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

const columns: ColumnDef<ProjectDetailRow>[] = [
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
  { accessorKey: 'region', header: 'Region' },
  { accessorKey: 'department', header: 'Department' },
]

export function ProjectUtilizationPage() {
  const { holding } = useParams<{ holding: string }>()

  // Reached from the sidebar with no project selected yet — show the
  // search picker instead of a param-less detail view.
  if (!holding) return <ProjectPickerPage />

  return <ProjectUtilizationDetail holding={holding} />
}

function ProjectUtilizationDetail({ holding }: { holding: string }) {
  const query = useProjectUtilization(holding)
  // /utilization/projects/{holding} only returns two pre-aggregated arrays
  // (by employee, by week) with no cross-dimension fields, so an Employee
  // filter can't narrow both charts from that response alone (a week row
  // has no employee breakdown). To make the Employee filter propagate to
  // *every* chart and the table (dashboard-design rule), both charts and
  // the detail table are instead derived here from the raw booking
  // records for this holding — same approach as the Employee Utilization
  // page's project/week charts.
  const recordsQuery = useUtilizationRecordsAll({ holding })

  const [employee, setEmployee] = React.useState<string | undefined>()

  const holdingRecords = recordsQuery.data?.items ?? []

  const employeeOptions = React.useMemo(
    () => Array.from(new Set(holdingRecords.map((r) => r.employee))).sort(),
    [holdingRecords],
  )

  // Total Employees = distinct employees with booking records on this
  // project/holding (unfiltered by the Employee filter — this KPI reflects
  // the whole holding, matching the other holding-level KPIs below).
  const totalEmployees = React.useMemo(
    () => new Set(holdingRecords.map((r) => r.employee)).size,
    [holdingRecords],
  )

  const filteredRecords = React.useMemo(
    () => holdingRecords.filter((r) => !employee || r.employee === employee),
    [holdingRecords, employee],
  )

  const employeeData = React.useMemo(() => {
    const totals = new Map<string, { 'Client Hours': number; 'Internal Hours': number }>()
    for (const r of filteredRecords) {
      const row = totals.get(r.employee) ?? { 'Client Hours': 0, 'Internal Hours': 0 }
      if (r.hours_type === 'Client Hours') row['Client Hours'] += r.hours
      else if (r.hours_type === 'Internal Hours') row['Internal Hours'] += r.hours
      totals.set(r.employee, row)
    }
    return withTruncatedLabels(
      Array.from(totals, ([name, hours]) => ({ name, ...hours })),
      'name',
    )
  }, [filteredRecords])

  const weekData = React.useMemo(() => {
    const totals = new Map<string, { 'Client Hours': number; 'Internal Hours': number }>()
    for (const r of filteredRecords) {
      const row = totals.get(r.week_start) ?? { 'Client Hours': 0, 'Internal Hours': 0 }
      if (r.hours_type === 'Client Hours') row['Client Hours'] += r.hours
      else if (r.hours_type === 'Internal Hours') row['Internal Hours'] += r.hours
      totals.set(r.week_start, row)
    }
    return Array.from(totals, ([week_start, hours]) => ({ week: week_start, ...hours })).sort(
      (a, b) => a.week.localeCompare(b.week),
    )
  }, [filteredRecords])

  const detailData = React.useMemo(
    () => (query.data?.detail ?? []).filter((d) => !employee || d.employee === employee),
    [query.data, employee],
  )

  const table = useReactTable({
    data: detailData,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  const chartsLoading = query.isLoading || recordsQuery.isLoading
  const chartsError = query.isError || recordsQuery.isError

  if (!query.isLoading && !query.isError && query.data === null) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-4">
          <Link to="/utilization/results" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            Back to results
          </Link>
          <Link to="/utilization/projects" className="text-sm text-primary hover:underline">
            Change project
          </Link>
        </div>
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-border bg-card p-12 text-center shadow-card">
          <FolderX className="h-10 w-10 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Project not found</h2>
          <p className="text-sm text-muted-foreground">
            No utilization records exist for "{holding}".
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-5">
      <div className="flex items-center gap-4">
        <Link to="/utilization/results" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Back to results
        </Link>
        <Link to="/utilization/projects" className="text-sm text-primary hover:underline">
          Change project
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Employees"
          value={totalEmployees}
          loading={recordsQuery.isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Total Hours"
          value={query.data ? query.data.total_hours.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
          loading={query.isLoading}
          icon={Clock}
          iconTone="blue"
        />
        <KpiCard
          label="Client Hours"
          value={query.data ? query.data.client_hours.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
          loading={query.isLoading}
          icon={Briefcase}
          iconTone="blue"
        />
        <KpiCard
          label="Internal Hours"
          value={query.data ? query.data.internal_hours.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
          loading={query.isLoading}
          icon={Building2}
          iconTone="blue"
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Total Hours by Employee and Hours Type"
          isLoading={chartsLoading}
          isError={chartsError}
          isEmpty={employeeData.length === 0}
        >
          <CustomBarChart
            data={employeeData}
            index="name"
            series={HOURS_TYPE_SERIES}
            yAxisLabel="Hours"
            layout="vertical"
            yAxisWidth={160}
            showLegend
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Total Hours by Week Start and Hours Type"
          isLoading={chartsLoading}
          isError={chartsError}
          isEmpty={weekData.length === 0}
        >
          <CustomBarChart
            data={weekData}
            index="week"
            series={HOURS_TYPE_SERIES}
            yAxisLabel="Hours"
            xAxisLabel="Week"
            showLegend
            className="h-full"
          />
        </ChartCard>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Detail</h2>
        <TableScrollContainer>
          <table className="w-full min-w-[720px] text-sm">
            <thead className="sticky top-0 z-10 bg-muted">
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
              {query.isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-t border-border">
                    {columns.map((_, j) => (
                      <td key={j} className="px-3 py-2">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : query.isError ? (
                <tr>
                  <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                    Couldn't load detail. Try refreshing.
                  </td>
                </tr>
              ) : table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                    No detail records.
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
          </table>
        </TableScrollContainer>
      </div>
      </div>

      <FiltersPanel>
        <FilterSelect label="Employee" value={employee} options={employeeOptions} onChange={setEmployee} />
      </FiltersPanel>
    </div>
  )
}
