import { useMemo } from 'react'
import { Users, UserCheck, UserX, UserPlus, UserMinus, TrendingDown, Layers } from 'lucide-react'
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table'

import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { FilterBar } from '@/components/dashboard/filter-bar'
import { CustomLineChart } from '@/components/dashboard/custom-line-chart'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { CustomDonutChart } from '@/components/dashboard/custom-donut-chart'
import { Skeleton } from '@/components/ui/skeleton'
import { type EmployeeRecord } from '@/lib/roster-api'
import { VOLUNTARY_COLORS, colorsForLabels } from '@/lib/chart-colors'
import { TableScrollContainer } from '@/components/dashboard/table-scroll-container'
import { applyEmployeeFilters } from '@/lib/employee-filters'
import { useHrAnalyticsFilters } from '@/lib/use-hr-analytics-filters'

// EmployeeRecord doesn't carry LWD/Reason for Leaving (see employee-filters.ts
// caveat), so this row shape merges the full employee directory with those
// two fields joined in by name from the exits_table (which does carry them).
// Matches the Power BI reference: full roster sorted by Name, mostly blank
// LWD/Reason except the genuinely inactive rows.
interface EmployeeTableRow extends EmployeeRecord {
  lwd: string | null
  reason_for_leaving: string | null
}

// Hoisted to module scope (rather than an inline literal in JSX) so its
// array reference is stable across renders, matching CustomBarChart's
// React.memo.
const JOINERS_VS_EXITS_SERIES = [
  { category: 'Joiners', color: 'indigo' },
  { category: 'Exits', color: 'terracotta' },
]

const exitColumns: ColumnDef<EmployeeTableRow>[] = [
  { accessorKey: 'name', header: 'Name' },
  { accessorKey: 'designation', header: 'Designation' },
  { accessorKey: 'primary_skill', header: 'Primary Skill' },
  { accessorKey: 'region', header: 'Region' },
  { accessorKey: 'market', header: 'Market' },
  { accessorKey: 'type', header: 'Type' },
  { accessorKey: 'lwd', header: 'LWD' },
  { accessorKey: 'reason_for_leaving', header: 'Reason for Leaving' },
  { accessorKey: 'status', header: 'Status' },
]

export function HrAnalyticsPage() {
  const { summary, trends, attrition, employeesQuery, filters, setFilter, filterDefs, monthFilter } =
    useHrAnalyticsFilters()

  // Status/Department/Region filter the roster directly (EmployeeRecord
  // carries those fields), so Total/Active/Inactive are recomputed from
  // the filtered employee list — same pattern as the exits table/donut
  // below. Joiners/Exits/Attrition % are date-based (DOJ/LWD aren't
  // exposed on EmployeeRecord — see employee-filters.ts caveat) so they
  // stay as the server-computed, unfiltered values.
  const employees = employeesQuery.data?.items ?? []
  const filteredEmployees = applyEmployeeFilters(employees, filters, {
    status: 'status',
    department: 'designation',
    region: 'region',
  })
  const totalEmployees = filteredEmployees.length
  const activeEmployees = filteredEmployees.filter((e) => e.status === 'Active').length
  const inactiveEmployees = filteredEmployees.filter((e) => e.status === 'Inactive').length

  // Memoized so an unrelated page re-render (e.g. the exits table below
  // changing its internal TanStack Table sort state) doesn't recreate these
  // arrays with new references and force every chart to redraw. `monthFilter`
  // is itself `useCallback`'d in the hook (keyed on filters.monthYear), so
  // depending on it here is both correct and stable.
  const headcountData = useMemo(
    () =>
      (trends.data?.month_wise_closing_headcount ?? [])
        .filter((m) => monthFilter(m.month))
        .map((m) => ({ month: m.month, 'Closing Headcount': m.closing_headcount })),
    [trends.data, monthFilter],
  )

  const joinersLeaversData = useMemo(
    () =>
      (trends.data?.monthly_joiners_vs_leavers ?? [])
        .filter((m) => monthFilter(m.month))
        .map((m) => ({ month: m.month, Joiners: m.joiners, Exits: m.exits })),
    [trends.data, monthFilter],
  )

  const resignationData = useMemo(
    () =>
      (attrition.data?.month_wise_resignation ?? [])
        .filter((m) => monthFilter(m.month))
        .map((m) => ({ month: m.month, Exits: m.exits })),
    [attrition.data, monthFilter],
  )

  // Voluntary/Involuntary split still comes from the exits_table, filtered
  // the same way as the KPIs above, so it stays in sync with the table below.
  const filteredExitsForDonut = useMemo(
    () =>
      applyEmployeeFilters(attrition.data?.exits_table ?? [], filters, {
        status: 'status',
        department: 'designation',
        region: 'region',
      }),
    [attrition.data, filters],
  )

  const voluntaryData = useMemo(
    () =>
      Object.entries(
        filteredExitsForDonut.reduce<Record<string, number>>((acc, e) => {
          const reason = e.reason_for_leaving ?? 'Unknown'
          acc[reason] = (acc[reason] ?? 0) + 1
          return acc
        }, {}),
      ).map(([name, value]) => ({ name, value })),
    [filteredExitsForDonut],
  )
  const voluntaryColors = useMemo(
    () => colorsForLabels(voluntaryData.map((d) => d.name), VOLUNTARY_COLORS),
    [voluntaryData],
  )

  // Bottom table: the FULL employee directory (matches the Power BI
  // reference, which is not filtered to exits-only), sorted alphabetically
  // by Name, with LWD/Reason for Leaving joined in by name from
  // exits_table since EmployeeRecord doesn't carry those two fields.
  const exitsByName = new Map(
    (attrition.data?.exits_table ?? []).map((e) => [e.name, e]),
  )
  const employeeTableRows: EmployeeTableRow[] = [...filteredEmployees]
    .sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''))
    .map((e) => {
      const exit = e.name ? exitsByName.get(e.name) : undefined
      return {
        ...e,
        lwd: exit?.lwd ?? null,
        reason_for_leaving: exit?.reason_for_leaving ?? null,
      }
    })

  const table = useReactTable({
    data: employeeTableRows,
    columns: exitColumns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <div className="space-y-5">
      <FilterBar filters={filterDefs} values={filters} onChange={setFilter} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-7">
        <KpiCard
          label="Total Employees"
          value={employeesQuery.data ? totalEmployees : '—'}
          loading={employeesQuery.isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Active"
          value={employeesQuery.data ? activeEmployees : '—'}
          loading={employeesQuery.isLoading}
          icon={UserCheck}
          iconTone="emerald"
        />
        <KpiCard
          label="Inactive"
          value={employeesQuery.data ? inactiveEmployees : '—'}
          loading={employeesQuery.isLoading}
          icon={UserX}
          iconTone="red"
        />
        <KpiCard
          label="Joiners"
          value={summary.data?.joiners ?? '—'}
          loading={summary.isLoading}
          provisional
          provisionalNote="Date-based (DOJ), not exposed on the employee directory row — not affected by Status/Department/Region filters above."
          icon={UserPlus}
          iconTone="emerald"
        />
        <KpiCard
          label="Exits"
          value={summary.data?.exits ?? '—'}
          loading={summary.isLoading}
          provisional
          provisionalNote="Date-based (LWD), not exposed on the employee directory row — not affected by Status/Department/Region filters above."
          icon={UserMinus}
          iconTone="red"
        />
        <KpiCard
          label="Attrition %"
          value={summary.data ? `${summary.data.attrition_pct.toFixed(1)}%` : '—'}
          loading={summary.isLoading}
          provisional
          provisionalNote="Attrition % measure is PROVISIONAL, see the data-model skill. Also not affected by the filters above — see in-code note."
          icon={TrendingDown}
          iconTone="blue"
        />
        <KpiCard
          label="Closing Headcount"
          value={summary.data?.closing_headcount ?? '—'}
          loading={summary.isLoading}
          provisional
          provisionalNote="Server-computed month-end headcount, not exposed per-row on the employee directory — not affected by Status/Department/Region filters above."
          icon={Layers}
          iconTone="blue"
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Month Wise Headcount"
          isLoading={trends.isLoading}
          isError={trends.isError}
          isEmpty={headcountData.length === 0}
        >
          <CustomLineChart
            data={headcountData}
            index="month"
            category="Closing Headcount"
            yAxisLabel="Employees"
            xAxisLabel="Month"
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Monthly Joiners vs Leavers"
          isLoading={trends.isLoading}
          isError={trends.isError}
          isEmpty={joinersLeaversData.length === 0}
        >
          <CustomBarChart
            data={joinersLeaversData}
            index="month"
            series={JOINERS_VS_EXITS_SERIES}
            yAxisLabel="Employees"
            xAxisLabel="Month"
            showLegend
            className="h-full"
          />
        </ChartCard>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Attrition drill-down</h2>
        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
          <ChartCard
            title="Month-Wise Resignation"
            isLoading={attrition.isLoading}
            isError={attrition.isError}
            isEmpty={resignationData.length === 0}
          >
            <CustomBarChart
              data={resignationData}
              index="month"
              category="Exits"
              color="red"
              yAxisLabel="Exits"
              xAxisLabel="Month"
              showLegend
              className="h-full"
            />
          </ChartCard>

          <ChartCard
            title="Voluntary vs Involuntary"
            isLoading={attrition.isLoading}
            isError={attrition.isError}
            isEmpty={voluntaryData.length === 0}
          >
            <CustomDonutChart
              data={voluntaryData}
              colors={voluntaryColors}
              totalLabel="Exits"
              className="h-full"
            />
          </ChartCard>
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Employees</h2>
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
              {employeesQuery.isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-t border-border">
                    {exitColumns.map((_, j) => (
                      <td key={j} className="px-3 py-2">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : employeesQuery.isError ? (
                <tr>
                  <td colSpan={exitColumns.length} className="px-3 py-6 text-center text-muted-foreground">
                    Couldn't load employees. Try refreshing.
                  </td>
                </tr>
              ) : table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={exitColumns.length} className="px-3 py-6 text-center text-muted-foreground">
                    No employees match this filter.
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
  )
}
