import { useMemo } from 'react'
import { Percent, Users, Gauge } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { CustomLineChart } from '@/components/dashboard/custom-line-chart'
import { CustomDonutChart } from '@/components/dashboard/custom-donut-chart'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { useUtilizationOverview } from '@/lib/utilization-api'
import { UTILIZATION_SPLIT_COLORS } from '@/lib/chart-colors'
import { withTruncatedLabels } from '@/lib/chart-labels'

export function UtilizationOverviewPage() {
  const overview = useUtilizationOverview()

  // Memoized, keyed on overview.data rather than the whole query object:
  // react-query re-renders this component on background-refetch state
  // changes (isFetching/dataUpdatedAt) even when `data` itself hasn't
  // changed, which would otherwise recreate these arrays and force the
  // now-React.memo'd charts to redraw for no reason.
  const trendData = useMemo(
    () =>
      overview.data?.weekly_trend.map((w) => ({
        week: w.week_start,
        'Avg Weekly Utilization %': +(w.avg_weekly_utilization_pct * 100).toFixed(1),
      })) ?? [],
    [overview.data],
  )

  const splitData = useMemo(
    () =>
      overview.data
        ? [
            { name: 'High', value: overview.data.utilization_split.high },
            { name: 'Moderate', value: overview.data.utilization_split.moderate },
            { name: 'Low', value: overview.data.utilization_split.low },
          ]
        : [],
    [overview.data],
  )
  const splitColors = useMemo(
    () => splitData.map((d) => UTILIZATION_SPLIT_COLORS[d.name] ?? 'gray'),
    [splitData],
  )

  const rankingData = useMemo(
    () =>
      withTruncatedLabels(
        overview.data?.employee_ranking.map((r) => ({
          name: r.employee,
          value: +(r.period_utilization_pct * 100).toFixed(1),
        })) ?? [],
        'name',
      ),
    [overview.data],
  )

  return (
    <div className="space-y-5">

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <KpiCard
          label="Average Period Utilization"
          value={overview.data ? `${(overview.data.average_period_utilization_pct * 100).toFixed(1)}%` : '—'}
          loading={overview.isLoading}
          icon={Percent}
          iconTone="blue"
        />
        <KpiCard
          label="Total Employees"
          value={overview.data?.total_employees ?? '—'}
          loading={overview.isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Latest Week Utilization"
          value={overview.data ? `${(overview.data.latest_week_utilization_pct * 100).toFixed(1)}%` : '—'}
          loading={overview.isLoading}
          icon={Gauge}
          iconTone="blue"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="Weekly Utilization Trend"
          isLoading={overview.isLoading}
          isError={overview.isError}
          isEmpty={trendData.length === 0}
        >
          <CustomLineChart
            data={trendData}
            index="week"
            category="Avg Weekly Utilization %"
            yAxisLabel="Utilization %"
            xAxisLabel="Week"
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Utilization Split"
          subtitle="High / Moderate / Low bands"
          isLoading={overview.isLoading}
          isError={overview.isError}
          isEmpty={splitData.every((d) => d.value === 0)}
          provisional
          provisionalNote="Utilization band thresholds (High/Moderate/Low) are PROVISIONAL — not yet confirmed against the real Power BI DAX. See the data-model skill."
        >
          <CustomDonutChart data={splitData} colors={splitColors} className="h-full" />
        </ChartCard>
      </div>

      <ChartCard
        title="Employee Period Utilization %"
        subtitle="Ranked, all employees"
        isLoading={overview.isLoading}
        isError={overview.isError}
        isEmpty={rankingData.length === 0}
        height="h-80"
      >
        {/* 41 employees at the page's normal chart height would squash
            every bar into an unreadable ~11px sliver, silently hiding most
            of the data even though it's all present in the DOM (the same
            failure mode flagged on Workforce's seniority chart). `rowHeightPx`
            gives each bar a fixed height and lets CustomBarChart scroll its
            plot internally instead. */}
        <CustomBarChart
          data={rankingData}
          index="name"
          category="value"
          tooltipValueLabel="Utilization %"
          layout="vertical"
          yAxisWidth={140}
          showLegend={false}
          rowHeightPx={32}
          className="h-full"
        />
      </ChartCard>
    </div>
  )
}
