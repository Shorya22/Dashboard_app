import { Users, UserCheck, UserX, UserPlus, UserMinus, TrendingDown, Layers } from 'lucide-react'
import { BarChart, DonutChart, Legend } from '@tremor/react'
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
import { FullLabelTooltip } from '@/components/dashboard/full-label-tooltip'
import { Skeleton } from '@/components/ui/skeleton'
import { type EmployeeRecord } from '@/lib/roster-api'
import { VOLUNTARY_COLORS, colorsForLabels } from '@/lib/chart-colors'
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

  const headcountData = (trends.data?.month_wise_closing_headcount ?? [])
    .filter((m) => monthFilter(m.month))
    .map((m) => ({ month: m.month, 'Closing Headcount': m.closing_headcount }))

  const joinersLeaversData = (trends.data?.monthly_joiners_vs_leavers ?? [])
    .filter((m) => monthFilter(m.month))
    .map((m) => ({ month: m.month, Joiners: m.joiners, Exits: m.exits }))

  const resignationData = (attrition.data?.month_wise_resignation ?? [])
    .filter((m) => monthFilter(m.month))
    .map((m) => ({ month: m.month, Exits: m.exits }))

  // Voluntary/Involuntary split still comes from the exits_table, filtered
  // the same way as the KPIs above, so it stays in sync with the table below.
  const filteredExitsForDonut = applyEmployeeFilters(attrition.data?.exits_table ?? [], filters, {
    status: 'status',
    department: 'designation',
    region: 'region',
  })

  const voluntaryData = Object.entries(
    filteredExitsForDonut.reduce<Record<string, number>>((acc, e) => {
      const reason = e.reason_for_leaving ?? 'Unknown'
      acc[reason] = (acc[reason] ?? 0) + 1
      return acc
    }, {}),
  ).map(([name, value]) => ({ name, value }))
  const voluntaryColors = colorsForLabels(voluntaryData.map((d) => d.name), VOLUNTARY_COLORS)

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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">HR Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Headcount, joiners/exits, and attrition
        </p>
      </div>

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
          iconTone="orange"
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
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
            color="orange"
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
            series={[
              { category: 'Joiners', color: 'orange' },
              { category: 'Exits', color: 'blue' },
            ]}
            yAxisLabel="Employees"
            xAxisLabel="Month"
            showLegend
            className="h-full"
          />
        </ChartCard>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Attrition drill-down</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ChartCard
            title="Month-Wise Resignation"
            isLoading={attrition.isLoading}
            isError={attrition.isError}
            isEmpty={resignationData.length === 0}
          >
            <BarChart
              data={resignationData}
              index="month"
              categories={['Exits']}
              colors={['red']}
              yAxisLabel="Exits"
              xAxisLabel="Month"
              customTooltip={FullLabelTooltip}
              showAnimation
              animationDuration={1000}
              className="h-full"
            />
          </ChartCard>

          <ChartCard
            title="Voluntary vs Involuntary"
            isLoading={attrition.isLoading}
            isError={attrition.isError}
            isEmpty={voluntaryData.length === 0}
          >
            <div className="flex h-full w-full flex-col items-center justify-center gap-4">
              <DonutChart
                data={voluntaryData}
                category="value"
                index="name"
                colors={voluntaryColors}
                customTooltip={FullLabelTooltip}
                showAnimation
                animationDuration={1000}
                className="h-44"
              />
              <div className="flex w-full justify-center">
                <Legend categories={voluntaryData.map((d) => d.name)} colors={voluntaryColors} className="max-w-full" />
              </div>
            </div>
          </ChartCard>
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Employees</h2>
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
        </div>
      </div>
    </div>
  )
}
