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

  const growthData =
    trends.data?.month_wise_closing_headcount.map((m) => ({
      month: m.month,
      'Closing Headcount': m.closing_headcount,
    })) ?? []

  // NOTE: this donut is titled "GCC vs Non-GCC" but actually renders the
  // Seniority Category breakdown — a title/legend mismatch present in the
  // source Power BI report itself, replicated here intentionally rather
  // than "fixed" to a literal GCC/Non-GCC split, per the parity audit.
  // Seniority Category mapping is PROVISIONAL (not confirmed against real
  // DAX). The reference PDF's legend for this donut shows exactly 4
  // segments (Senior/Lead/Mid/Other) with no separate "TBD" slice, so we
  // merge TBD into Other client-side for THIS donut's display only — the
  // underlying `workforce_by_seniority_category` breakdown from the API is
  // left untouched since other pages may rely on TBD being distinct.
  const seniorityCategoryData = breakdowns.data
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
    : []
  const seniorityCategoryColors = colorsForLabels(
    seniorityCategoryData.map((d) => d.name),
    SENIORITY_CATEGORY_COLORS,
  )

  const utilizationSplitData = booking.data
    ? [
        { name: 'Client Hours', value: booking.data.client_hours },
        { name: 'Internal Hours', value: booking.data.internal_hours },
      ]
    : []
  const utilizationSplitColors = colorsForLabels(
    utilizationSplitData.map((d) => d.name),
    HOURS_TYPE_COLORS,
  )

  const categoryData = breakdowns.data
    ? Object.entries(breakdowns.data.workforce_category_split).map(
        ([name, value]) => ({
          name,
          value,
        }),
      )
    : []
  const categoryColors = colorsForLabels(
    categoryData.map((d) => d.name),
    WORKFORCE_CATEGORY_COLORS,
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Home</h1>
        <p className="text-sm text-muted-foreground">
          Workforce overview at a glance
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
          iconTone="orange"
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
          color="orange"
          yAxisLabel="Employees"
          xAxisLabel="Month"
          className="h-full"
        />
      </ChartCard>

      {/* All 3 donuts side-by-side in one row, left-to-right order matching
          the reference: Internal v Client Utilization, GCC vs Non-GCC,
          Workforce Category. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard
          title="Internal v Client Utilization"
          subtitle="Client Hours vs Internal Hours"
          isLoading={booking.isLoading}
          isError={booking.isError}
          isEmpty={utilizationSplitData.length === 0}
          height="h-64"
        >
          <CustomDonutChart
            data={utilizationSplitData}
            colors={utilizationSplitColors}
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="GCC vs Non-GCC"
          subtitle="Seniority Category"
          isLoading={breakdowns.isLoading}
          isError={breakdowns.isError}
          isEmpty={seniorityCategoryData.length === 0}
          provisional
          provisionalNote="Title/legend mismatch replicated from the source Power BI report as-is: this donut is titled 'GCC vs Non-GCC' but shows the Seniority Category split (Senior/Lead/Mid/Other/TBD), which is itself a PROVISIONAL mapping not confirmed against real DAX."
          height="h-64"
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
          height="h-64"
        >
          <CustomDonutChart
            data={categoryData}
            colors={categoryColors}
            className="h-full"
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card
          className="group cursor-pointer rounded-2xl border-border bg-card p-5 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover"
          onClick={() => navigate('/hr-portal')}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-orange/10 text-accent-orange">
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
          className="group cursor-pointer rounded-2xl border-border bg-card p-5 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover"
          onClick={() => navigate('/utilization')}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-orange/10 text-accent-orange">
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
