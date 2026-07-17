import * as React from 'react'
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { ArrowUpDown, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { FilterBar } from '@/components/dashboard/filter-bar'
import { TableScrollContainer } from '@/components/dashboard/table-scroll-container'
import { useRosterEmployeesAll, type EmployeeRecord } from '@/lib/roster-api'
import {
  ALL,
  buildOptions,
  compareGrade,
  deriveSeniorityCategory,
  distinctNormalizedValues,
  distinctValues,
  normalizeDesignationLabel,
  type FilterValues,
} from '@/lib/employee-filters'

const columns: ColumnDef<EmployeeRecord>[] = [
  { accessorKey: 'employee_id', header: 'Employee ID' },
  { accessorKey: 'name', header: 'Name' },
  {
    accessorKey: 'grade',
    header: 'Grade',
    sortingFn: (rowA, rowB) => compareGrade(rowA.original.grade, rowB.original.grade),
  },
  { accessorKey: 'designation', header: 'Designation' },
  { accessorKey: 'work_location', header: 'Work Location' },
  {
    accessorKey: 'total_experience',
    header: 'Total Experience',
    cell: (info) => {
      const v = info.getValue<number | null>()
      return v == null ? '—' : `${v.toFixed(1)} yrs`
    },
  },
  { accessorKey: 'region', header: 'Region' },
  { accessorKey: 'market', header: 'Market' },
  { accessorKey: 'primary_skill', header: 'Primary Skill' },
  { accessorKey: 'status', header: 'Status' },
]

const PAGE_SIZES = [10, 25, 50]

export function EmployeeDirectoryPage() {
  const [pageSize, setPageSize] = React.useState(25)
  const [pageIndex, setPageIndex] = React.useState(0)
  const [nameSearch, setNameSearch] = React.useState('')
  const [sorting, setSorting] = React.useState<SortingState>([])

  // Fetches the full 52-row roster once and does all filtering/pagination
  // client-side, since /roster/employees has no filter query params — see
  // lib/employee-filters.ts for the shared rationale.
  const { data, isLoading, isError, isFetching } = useRosterEmployeesAll()
  const allEmployees = data?.items ?? []

  const [filters, setFilters] = React.useState<FilterValues>({
    department: ALL,
    allocation: ALL,
    seniorityCategory: ALL,
    region: ALL,
  })
  const setFilter = (key: string, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }))

  const filterDefs = [
    {
      key: 'department',
      label: 'Department',
      // Designation has a casing-duplicate data-quality issue ("SalesForce
      // Core Developer" vs "Salesforce Core Developer") — normalize before
      // building dropdown options so it doesn't show two entries for the
      // same job title (same bug class already fixed for the Departments
      // KPI and the Primary Skill filter elsewhere).
      options: buildOptions(distinctNormalizedValues(allEmployees, 'designation', normalizeDesignationLabel)),
    },
    {
      key: 'allocation',
      label: 'Allocation',
      options: buildOptions(distinctValues(allEmployees, 'client')),
    },
    {
      key: 'seniorityCategory',
      label: 'Seniority Category',
      options: buildOptions(
        Array.from(new Set(allEmployees.map((e) => deriveSeniorityCategory(e.seniority_level)))).sort(),
      ),
    },
    {
      key: 'region',
      label: 'Region/Market',
      options: buildOptions(distinctValues(allEmployees, 'region')),
    },
  ]

  // NAME stays a free-text search-as-you-type field per the reference; the
  // other four are proper dropdowns.
  const filtered = React.useMemo(() => {
    return allEmployees.filter((e) => {
      if (nameSearch.trim() && !(e.name ?? '').toLowerCase().includes(nameSearch.trim().toLowerCase())) {
        return false
      }
      if (
        filters.department !== ALL &&
        normalizeDesignationLabel(e.designation ?? '') !== filters.department
      ) {
        return false
      }
      if (filters.allocation !== ALL && e.client !== filters.allocation) return false
      if (filters.region !== ALL && e.region !== filters.region) return false
      if (
        filters.seniorityCategory !== ALL &&
        deriveSeniorityCategory(e.seniority_level) !== filters.seniorityCategory
      ) {
        return false
      }
      return true
    })
  }, [allEmployees, nameSearch, filters])

  // Sorting must apply to the full FILTERED set before pagination slices
  // it, not just to whichever rows happen to already be on the current
  // page — otherwise clicking a column header only reorders the 25 (or
  // however many) rows currently visible instead of the whole result set.
  // Feed the table the full `filtered` array and let it own sorting; only
  // slice for display after sorting has been applied.
  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  // Pagination footer recomputes from the FILTERED count, not the
  // unfiltered roster total — this is the bug fix: previously the page
  // fetched one server page at a time and filtered only within it, so
  // narrowing a filter never changed "Page X of Y".
  const total = filtered.length
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const clampedPageIndex = Math.min(pageIndex, pageCount - 1)
  const sortedRows = table.getSortedRowModel().rows
  const pageRows = sortedRows.slice(clampedPageIndex * pageSize, clampedPageIndex * pageSize + pageSize)

  React.useEffect(() => {
    setPageIndex(0)
  }, [nameSearch, filters, pageSize])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by name…"
            value={nameSearch}
            onChange={(e) => setNameSearch(e.target.value)}
            className="pl-8"
          />
        </div>
        <FilterBar filters={filterDefs} values={filters} onChange={setFilter} />
      </div>

      <div className="flex justify-end">
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="page-size" className="text-muted-foreground">
            Rows per page
          </label>
          <select
            id="page-size"
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
                    onClick={header.column.getToggleSortingHandler()}
                    className="cursor-pointer select-none whitespace-nowrap px-3 py-2 text-left font-medium"
                  >
                    <span className="inline-flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                      {header.column.getIsSorted() === 'asc' && ' ▲'}
                      {header.column.getIsSorted() === 'desc' && ' ▼'}
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-t border-border">
                  {columns.map((_, j) => (
                    <td key={j} className="px-3 py-2">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  ))}
                </tr>
              ))
            ) : isError ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                  Couldn't load the employee directory. Try refreshing.
                </td>
              </tr>
            ) : pageRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                  No employees match these filters.
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
          Page {clampedPageIndex + 1} of {pageCount} {isFetching && '· updating…'}
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
