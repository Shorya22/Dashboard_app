import { useMemo } from 'react'
import { Card } from '@tremor/react'
import { Users, Target, Building2, Clock, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { CustomLineChart } from '@/components/dashboard/custom-line-chart'
import { CustomDonutChart } from '@/components/dashboard/custom-donut-chart'
import { Button } from '@/components/ui/button'
import {
  useBookingSummary,
  useRosterBreakdowns,
  useRosterSummary,
  useRosterTrends,
} from '@/lib/roster-api'
import {
  WORKFORCE_CATEGORY_COLORS,
  SENIORITY_CATEGORY_COLORS,
  HOURS_TYPE_COLORS,
  colorsForLabels,
} from '@/lib/chart-colors'

export function HomePage() {
  const navigate = useNavigate()
  const summary = useRosterSummary()
  const breakdowns = useRosterBreakdowns()
  const trends = useRosterTrends()
  const booking = useBookingSummary()

  // Memoized, keyed on each query's `.data` rather than the whole query
  // object: react-query re-renders this component on background-refetch
  // state changes (isFetching/dataUpdatedAt) even when `data` itself hasn't
  // changed, which would otherwise recreate these arrays and force the
  // now-React.memo'd charts (custom-line-chart.tsx / custom-donut-chart.tsx)
  // to redraw for no reason.
  const growthData = useMemo(
    () =>
      (trends.data?.month_wise_closing_headcount ?? []).map((m) => ({
        month: m.month,
        'Closing Headcount': m.closing_headcount,
      })),
    [trends.data],
  )

  // Seniority Category mapping is PROVISIONAL (not confirmed against real
  // DAX). The reference PDF's legend for this donut shows exactly 4
  // segments (Senior/Lead/Mid/Other) with no separate "TBD" slice, so we
  // merge TBD into Other client-side for THIS donut's display only — the
  // underlying `workforce_by_seniority_category` breakdown from the API is
  // left untouched since other pages may rely on TBD being distinct.
  const seniorityCategoryData = useMemo(
    () =>
      breakdowns.data
        ? Object.entries(breakdowns.data.workforce_by_seniority_category).reduce<
            { name: string; value: number }[]
          >((acc, [name, value]) => {
            const mergedName = name === 'TBD' ? 'Other' : name
            const existing = acc.find((d) => d.name === mergedName)
            if (existing) {
              existing.value += value
            } else {
              acc.push({ name: mergedName, value })
            }
            return acc
          }, [])
        : [],
    [breakdowns.data],
  )
  const seniorityCategoryColors = useMemo(
    () =>
      colorsForLabels(
        seniorityCategoryData.map((d) => d.name),
        SENIORITY_CATEGORY_COLORS,
      ),
    [seniorityCategoryData],
  )

  // From the chart declared in booking_metrics.yaml, so the slices are
  // whatever `Booked Hours Type` contains. Hardcoding the two labels here
  // meant a third category (e.g. "Leave Hours") would count toward the
  // total but appear in neither slice.
  const utilizationSplitData = useMemo(
    () =>
      Object.entries(booking.data?.hours_split ?? {}).map(([name, value]) => ({
        name,
        value: Number(value),
      })),
    [booking.data],
  )
  const utilizationSplitColors = useMemo(
    () =>
      colorsForLabels(
        utilizationSplitData.map((d) => d.name),
        HOURS_TYPE_COLORS,
      ),
    [utilizationSplitData],
  )

  const categoryData = useMemo(
    () =>
      breakdowns.data
        ? Object.entries(breakdowns.data.workforce_category_split).map(([name, value]) => ({
            name,
            value,
          }))
        : [],
    [breakdowns.data],
  )
  const categoryColors = useMemo(
    () =>
      colorsForLabels(
        categoryData.map((d) => d.name),
        WORKFORCE_CATEGORY_COLORS,
      ),
    [categoryData],
  )

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard
          label="Active Employees"
          value={summary.data?.active_employees ?? '—'}
          loading={summary.isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Strategic Pool"
          value={breakdowns.data?.strategic_pool ?? '—'}
          loading={breakdowns.isLoading}
          icon={Target}
          iconTone="blue"
        />
        <KpiCard
          label="Closing Headcount"
          value={summary.data?.closing_headcount ?? '—'}
          loading={summary.isLoading}
          icon={Building2}
          iconTone="blue"
        />
      </div>

      {/* Line chart, full-width, alone in its own row — matches the Power BI
          reference Home page layout (donuts moved into their own row below). */}
      <ChartCard
        title="Month-wise Workforce Growth"
        subtitle="Closing headcount, Jul 2025 – Jun 2026"
        isLoading={trends.isLoading}
        isError={trends.isError}
        isEmpty={growthData.length === 0}
      >
        <CustomLineChart
          data={growthData}
          index="month"
          category="Closing Headcount"
          yAxisLabel="Employees"
          xAxisLabel="Month"
          className="h-full"
        />
      </ChartCard>

      {/* All 3 donuts side-by-side in one row, left-to-right order matching
          the reference: Internal v Client Utilization, Workforce by Seniority,
          Workforce Category. */}
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
        <ChartCard
          title="Internal v Client Utilization"
          subtitle="Client Hours vs Internal Hours"
          isLoading={booking.isLoading}
          isError={booking.isError}
          isEmpty={utilizationSplitData.length === 0}
          height="h-56"
        >
          <CustomDonutChart
            data={utilizationSplitData}
            colors={utilizationSplitColors}
            totalLabel="Total Hours"
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Workforce by Seniority"
          subtitle="Seniority Category"
          isLoading={breakdowns.isLoading}
          isError={breakdowns.isError}
          isEmpty={seniorityCategoryData.length === 0}
          provisional
          provisionalNote="Seniority Category mapping is PROVISIONAL, not confirmed against real DAX."
          height="h-56"
        >
          <CustomDonutChart
            data={seniorityCategoryData}
            colors={seniorityCategoryColors}
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Workforce Category"
          subtitle="Active vs Strategic Pool"
          isLoading={breakdowns.isLoading}
          isError={breakdowns.isError}
          isEmpty={categoryData.length === 0}
          height="h-56"
        >
          <CustomDonutChart
            data={categoryData}
            colors={categoryColors}
            className="h-full"
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-2">
        <Card
          className="group cursor-pointer rounded-2xl border-border bg-card p-5 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          role="button"
          tabIndex={0}
          onClick={() => navigate('/hr-portal')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              navigate('/hr-portal')
            }
          }}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Building2 className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">HR Portal</p>
                <p className="text-xs text-muted-foreground">
                  Status, region, entity, and experience breakdowns
                </p>
              </div>
            </div>
            <Button
              variant="default"
              size="sm"
              className="shrink-0"
              onClick={(e) => {
                e.stopPropagation()
                navigate('/hr-portal')
              }}
            >
              Open <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Button>
          </div>
        </Card>

        <Card
          className="group cursor-pointer rounded-2xl border-border bg-card p-5 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          role="button"
          tabIndex={0}
          onClick={() => navigate('/utilization')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              navigate('/utilization')
            }
          }}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Clock className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">Utilization Portal</p>
                <p className="text-xs text-muted-foreground">
                  Client vs internal hours, weekly trend, and project search
                </p>
              </div>
            </div>
            <Button
              variant="default"
              size="sm"
              className="shrink-0"
              onClick={(e) => {
                e.stopPropagation()
                navigate('/utilization')
              }}
            >
              Open <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Button>
          </div>
        </Card>
      </div>
    </div>
  )
}
