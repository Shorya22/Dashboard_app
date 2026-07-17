import {
  Bell,
  BarChart3,
  Clock,
  FolderKanban,
  GraduationCap,
  Home,
  TrendingUp,
  User,
  Users,
} from 'lucide-react'

import { cn } from '@/lib/utils'

// Slim rail icons mirror the real app's sidebar nav (Home / Workforce /
// Skills / Utilization / Projects) so the preview reads as this product's
// actual shell, not a generic mockup.
const NAV_ICONS = [Home, Users, GraduationCap, Clock, FolderKanban]

// STATIC SNAPSHOT of the real dashboard's current figures (Active Employees
// / Strategic Pool / Closing Headcount), used only so this decorative hero
// preview reads like a real product screenshot. NOT wired to live data — it
// will not update as the underlying numbers change, and must never be
// treated as a source of truth. See the note in welcome-page.tsx.
const KPIS = [
  { label: 'Active Employees', value: '43', icon: Users },
  { label: 'Strategic Pool', value: '2', icon: TrendingUp },
  { label: 'Closing Headcount', value: '45', icon: BarChart3 },
]

const SENIORITY_BARS = ['w-[88%]', 'w-[62%]', 'w-[40%]']

/**
 * Decorative floating "dashboard preview" for the landing-page hero. Purely
 * presentational — mirrors the real Home screen's structure (mini sidebar,
 * KPI row, workforce-growth line, distribution donut, seniority bars) using
 * the app's own semantic color tokens, so it looks like a real screenshot
 * while staying obviously illustrative (shapes for chart values, a static
 * snapshot for KPIs — no live data wiring). Entrance/float motion is applied
 * by the parent.
 */
export function DashboardPreview({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'overflow-hidden rounded-2xl border border-border bg-card shadow-2xl',
        className,
      )}
      role="img"
      aria-label="Preview of the DEPT | Hexaware workforce analytics dashboard"
    >
      <div className="flex">
        {/* mini sidebar rail — evokes the real navy app shell */}
        <div className="hidden w-12 shrink-0 flex-col items-center gap-4 bg-primary py-4 sm:flex">
          <div className="h-5 w-5 rounded-md bg-white/90" />
          <div className="mt-1 flex flex-col gap-3">
            {NAV_ICONS.map((Icon, i) => (
              <div
                key={i}
                className={cn(
                  'flex h-7 w-7 items-center justify-center rounded-lg',
                  i === 0 && 'bg-white/20',
                )}
              >
                <Icon className="h-3.5 w-3.5 text-white/80" />
              </div>
            ))}
          </div>
        </div>

        {/* content area */}
        <div className="min-w-0 flex-1 p-4 sm:p-5">
          {/* header */}
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-bold text-foreground">Welcome back</p>
              <p className="text-[11px] text-muted-foreground">Workforce overview at a glance</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted">
                <Bell className="h-3.5 w-3.5 text-muted-foreground" />
              </div>
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary">
                <User className="h-3.5 w-3.5 text-primary-foreground" />
              </div>
            </div>
          </div>

          {/* KPI row */}
          <div className="mb-3 grid grid-cols-3 gap-2.5">
            {KPIS.map((kpi) => (
              <div key={kpi.label} className="rounded-xl border border-border bg-background p-2.5">
                <div className="mb-1.5 flex items-center justify-between gap-1">
                  <p className="truncate text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {kpi.label}
                  </p>
                  <kpi.icon className="h-3 w-3 shrink-0 text-primary/60" />
                </div>
                <p className="text-lg font-extrabold leading-none text-foreground">{kpi.value}</p>
              </div>
            ))}
          </div>

          {/* workforce-growth line chart */}
          <div className="mb-3 rounded-xl border border-border bg-background p-3">
            <p className="mb-2 text-[10px] font-semibold text-muted-foreground">
              Month-wise Workforce Growth
            </p>
            <svg
              viewBox="0 0 260 70"
              className="h-16 w-full"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="lp-area" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(215 70% 38%)" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="hsl(215 70% 38%)" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path
                d="M0,60 L26,56 L52,50 L78,48 L104,40 L130,30 L156,22 L182,12 L208,16 L234,10 L260,8 L260,70 L0,70 Z"
                fill="url(#lp-area)"
              />
              <polyline
                points="0,60 26,56 52,50 78,48 104,40 130,30 156,22 182,12 208,16 234,10 260,8"
                fill="none"
                stroke="hsl(215 70% 38%)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          {/* bottom row: distribution donut + seniority bars */}
          <div className="grid grid-cols-2 gap-2.5">
            <div className="rounded-xl border border-border bg-background p-3">
              <p className="mb-2 text-[10px] font-semibold text-muted-foreground">Client v Internal</p>
              <div className="flex items-center gap-3">
                <div
                  className="relative h-12 w-12 shrink-0 rounded-full"
                  style={{
                    background:
                      'conic-gradient(hsl(215 70% 38%) 0% 66%, hsl(168 64% 46%) 66% 100%)',
                  }}
                >
                  <div className="absolute inset-[26%] rounded-full bg-background" />
                </div>
                <div className="space-y-1">
                  <span className="flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: 'hsl(215 70% 38%)' }}
                    />
                    <span className="text-[9px] text-muted-foreground">Client</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: 'hsl(168 64% 46%)' }}
                    />
                    <span className="text-[9px] text-muted-foreground">Internal</span>
                  </span>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-background p-3">
              <p className="mb-2 text-[10px] font-semibold text-muted-foreground">By Seniority</p>
              <div className="space-y-2 pt-0.5">
                {SENIORITY_BARS.map((w, i) => (
                  <div key={i} className="h-2 rounded-full bg-muted">
                    <div className={cn('h-2 rounded-full bg-primary/80', w)} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
