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

  const trendData =
    overview.data?.weekly_trend.map((w) => ({
      week: w.week_start,
      'Avg Weekly Utilization %': +(w.avg_weekly_utilization_pct * 100).toFixed(1),
    })) ?? []

  const splitData = overview.data
    ? [
        { name: 'High', value: overview.data.utilization_split.high },
        { name: 'Moderate', value: overview.data.utilization_split.moderate },
        { name: 'Low', value: overview.data.utilization_split.low },
      ]
    : []
  const splitColors = splitData.map((d) => UTILIZATION_SPLIT_COLORS[d.name] ?? 'gray')

  const rankingData = withTruncatedLabels(
    overview.data?.employee_ranking.map((r) => ({
      name: r.employee,
      value: +(r.period_utilization_pct * 100).toFixed(1),
    })) ?? [],
    'name',
  )

  return (
    <div className="space-y-6">

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
            color="indigo"
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
        height="h-[28rem]"
      >
        {/* 41 employees at the page's normal chart height would squash
            every bar into an unreadable ~11px sliver, silently hiding most
            of the data even though it's all present in the DOM (the same
            failure mode flagged on Workforce's seniority chart). Instead,
            give each bar a fixed pixel height inside a vertically
            scrollable container so every bar + label stays legible and the
            full 41-row set is reachable by scrolling. */}
        <div className="h-full overflow-y-auto">
          <div style={{ height: `${rankingData.length * 32}px` }}>
            <CustomBarChart
              data={rankingData}
              index="name"
              category="value"
              color="indigo"
              layout="vertical"
              yAxisWidth={140}
              showLegend={false}
              className="h-full"
            />
          </div>
        </div>
      </ChartCard>
    </div>
  )
}
