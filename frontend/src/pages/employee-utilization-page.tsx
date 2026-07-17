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
import { ArrowLeft, ArrowUpDown, ChevronLeft, ChevronRight, Clock, Briefcase, Building2, FolderKanban, UserX, Search } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { FilterSelect } from '@/components/dashboard/filter-select'
import { FiltersPanel } from '@/components/dashboard/filters-panel'
import { HierarchicalMultiSelect, type HierarchicalItem } from '@/components/dashboard/hierarchical-multi-select'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { TableScrollContainer } from '@/components/dashboard/table-scroll-container'
import { withTruncatedLabels } from '@/lib/chart-labels'
import { colorsForLabels, HOURS_TYPE_COLORS } from '@/lib/chart-colors'
import { useEmployeeUtilization, useUtilizationRecordsAll } from '@/lib/utilization-api'

const fmtHours = (v: number) =>
  v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

interface EmployeeSummaryRow {
  employee: string
  totalHours: number
  clientHours: number
  internalHours: number
  totalProjects: number
}

const PAGE_SIZES = [25, 50, 100]

/** Landing state for `/utilization/employees` (no `:employee` param) —
 * reached from the sidebar rather than a drill-through click. Shows one
 * row per employee with aggregated totals (client-side groupby over the
 * raw booking records), a name search box, and sortable columns. Clicking
 * a row navigates to the existing `/utilization/employees/:employee`
 * detail route. */
function EmployeePickerPage() {
  
  const recordsQuery = useUtilizationRecordsAll({})
  const [search, setSearch] = React.useState('')
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [pageSize, setPageSize] = React.useState(25)
  const [pageIndex, setPageIndex] = React.useState(0)

  const summaryRows = React.useMemo<EmployeeSummaryRow[]>(() => {
    const totals = new Map<
      string,
      { totalHours: number; clientHours: number; internalHours: number; projects: Set<string> }
    >()
    for (const r of recordsQuery.data?.items ?? []) {
      const row = totals.get(r.employee) ?? {
        totalHours: 0,
        clientHours: 0,
        internalHours: 0,
        projects: new Set<string>(),
      }
      row.totalHours += r.hours
      if (r.hours_type === 'Client Hours') row.clientHours += r.hours
      else if (r.hours_type === 'Internal Hours') row.internalHours += r.hours
      row.projects.add(r.project)
      totals.set(r.employee, row)
    }
    return Array.from(totals, ([employee, v]) => ({
      employee,
      totalHours: v.totalHours,
      clientHours: v.clientHours,
      internalHours: v.internalHours,
      totalProjects: v.projects.size,
    })).sort((a, b) => a.employee.localeCompare(b.employee))
  }, [recordsQuery.data])

  const filteredRows = React.useMemo(() => {
    if (!search.trim()) return summaryRows
    const q = search.trim().toLowerCase()
    return summaryRows.filter((r) => r.employee.toLowerCase().includes(q))
  }, [summaryRows, search])

  const columns = React.useMemo<ColumnDef<EmployeeSummaryRow>[]>(
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
        accessorKey: 'employee',
        header: 'Employee Name',
        cell: ({ getValue, row }) => (
          <Link
            to={`/utilization/employees/${encodeURIComponent(row.original.employee)}`}
            className="font-medium text-primary hover:underline"
          >
            {getValue<string>()}
          </Link>
        ),
      },
      {
        accessorKey: 'totalHours',
        header: 'Total Hours',
        cell: ({ getValue }) => fmtHours(getValue<number>()),
      },
      {
        accessorKey: 'clientHours',
        header: 'Client Hours',
        cell: ({ getValue }) => fmtHours(getValue<number>()),
      },
      {
        accessorKey: 'internalHours',
        header: 'Internal Hours',
        cell: ({ getValue }) => fmtHours(getValue<number>()),
      },
      { accessorKey: 'totalProjects', header: 'Total Projects' },
      {
        id: 'view',
        header: '',
        cell: ({ row }) => (
          <Link
            to={`/utilization/employees/${encodeURIComponent(row.original.employee)}`}
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
            placeholder="Search employees…"
            className="pl-8"
          />
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="employee-page-size" className="text-muted-foreground">
            Rows per page
          </label>
          <select
            id="employee-page-size"
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
          <thead className="sticky top-0 bg-muted/50">
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
                  Couldn't load employees. Try refreshing.
                </td>
              </tr>
            ) : pageRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                  {summaryRows.length === 0 ? 'No employees available.' : `No matches for "${search}".`}
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

      <div className="flex items-center justify-between text-sm">
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

const HOURS_TYPES = ['Client Hours', 'Internal Hours']

const MONTH_FMT = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' })
const DAY_FMT = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })

/** Groups ISO week-start dates ("2026-05-04") into month parents ("May
 * 2026") with each date as a labelled child ("04 May 2026"). */
function weeksToHierarchy(weeks: string[]): HierarchicalItem[] {
  return weeks.map((week) => {
    const d = new Date(`${week}T00:00:00`)
    return { value: week, label: DAY_FMT.format(d), parent: MONTH_FMT.format(d) }
  })
}

// The /employees/{name} endpoint only returns two pre-aggregated arrays
// (by project, by week) with no cross-dimension fields — a project row has
// no hours-type/week breakdown and a week row has no project breakdown. To
// let Hours Type/Project/Week filters propagate to *both* charts (required
// by the dashboard-design filter rule), both charts are instead derived
// here from the raw booking records for this employee, fetched once via
// the same records-paginating hook the Results page uses. The 258-row
// booking sheet is small enough to fetch in full and filter client-side —
// there's no server-side `employee` filter on /utilization/records.
export function EmployeeUtilizationPage() {
  const { employee } = useParams<{ employee: string }>()

  // Reached from the sidebar with no employee selected yet — show the
  // search picker instead of a param-less detail view.
  if (!employee) return <EmployeePickerPage />

  return <EmployeeUtilizationDetail employee={employee} />
}

function EmployeeUtilizationDetail({ employee }: { employee: string }) {
  const query = useEmployeeUtilization(employee)
  const recordsQuery = useUtilizationRecordsAll({})

  const [hoursType, setHoursType] = React.useState<string | undefined>()
  const [project, setProject] = React.useState<string | undefined>()
  const [weeks, setWeeks] = React.useState<string[]>([])

  const employeeRecords = React.useMemo(
    () => (recordsQuery.data?.items ?? []).filter((r) => r.employee === employee),
    [recordsQuery.data, employee],
  )

  const projectOptions = React.useMemo(
    () => Array.from(new Set(employeeRecords.map((r) => r.project))).sort(),
    [employeeRecords],
  )
  const weekOptions = React.useMemo(
    () => Array.from(new Set(employeeRecords.map((r) => r.week_start))).sort(),
    [employeeRecords],
  )
  const weekHierarchy = React.useMemo(() => weeksToHierarchy(weekOptions), [weekOptions])

  const filteredRecords = React.useMemo(
    () =>
      employeeRecords.filter(
        (r) =>
          (!hoursType || r.hours_type === hoursType) &&
          (!project || r.project === project) &&
          (weeks.length === 0 || weeks.includes(r.week_start)),
      ),
    [employeeRecords, hoursType, project, weeks],
  )

  const projectData = React.useMemo(() => {
    const totals = new Map<string, number>()
    for (const r of filteredRecords) {
      totals.set(r.project, (totals.get(r.project) ?? 0) + r.hours)
    }
    return withTruncatedLabels(
      Array.from(totals, ([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value),
      'name',
    )
  }, [filteredRecords])

  const weekCategories = hoursType ? [hoursType] : HOURS_TYPES

  const weekData = React.useMemo(() => {
    const totals = new Map<string, { 'Client Hours': number; 'Internal Hours': number }>()
    for (const r of filteredRecords) {
      const row = totals.get(r.week_start) ?? { 'Client Hours': 0, 'Internal Hours': 0 }
      if (r.hours_type === 'Client Hours') row['Client Hours'] += r.hours
      else if (r.hours_type === 'Internal Hours') row['Internal Hours'] += r.hours
      totals.set(r.week_start, row)
    }
    return Array.from(totals, ([week_start, hours]) => ({ week: week_start, ...hours })).sort((a, b) =>
      a.week.localeCompare(b.week),
    )
  }, [filteredRecords])

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
          <Link to="/utilization/employees" className="text-sm text-primary hover:underline">
            Change employee
          </Link>
        </div>
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-border bg-card p-12 text-center shadow-card">
          <UserX className="h-10 w-10 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Employee not found</h2>
          <p className="text-sm text-muted-foreground">
            No utilization records exist for "{employee}".
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
        <Link to="/utilization/employees" className="text-sm text-primary hover:underline">
          Change employee
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
        <KpiCard
          label="Total Projects"
          value={query.data?.total_projects ?? '—'}
          loading={query.isLoading}
          icon={FolderKanban}
          iconTone="blue"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="Total Hours by Project"
          isLoading={chartsLoading}
          isError={chartsError}
          isEmpty={projectData.length === 0}
        >
          <CustomBarChart
            data={projectData}
            index="name"
            category="value"
            color="indigo"
            tooltipValueLabel="Hours"
            yAxisLabel="Hours"
            layout="vertical"
            yAxisWidth={160}
            showLegend={false}
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Total Hours by Week Start"
          subtitle="By hours type"
          isLoading={chartsLoading}
          isError={chartsError}
          isEmpty={weekData.length === 0}
        >
          <CustomBarChart
            data={weekData}
            index="week"
            series={weekCategories.map((c) => ({ category: c, color: colorsForLabels([c], HOURS_TYPE_COLORS)[0] }))}
            yAxisLabel="Hours"
            xAxisLabel="Week"
            showLegend
            className="h-full"
          />
        </ChartCard>
      </div>
      </div>

      <FiltersPanel>
        <FilterSelect label="Hours Type" value={hoursType} options={HOURS_TYPES} onChange={setHoursType} />
        <FilterSelect label="Project" value={project} options={projectOptions} onChange={setProject} />
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">Month Year, Week Start</label>
          <HierarchicalMultiSelect
            items={weekHierarchy}
            selected={weeks}
            onChange={setWeeks}
            placeholder="All Month Year, Week Start"
            className="w-[180px]"
          />
        </div>
      </FiltersPanel>
    </div>
  )
}
