import * as React from 'react'
import { NavLink } from 'react-router-dom'
import {
  Home,
  BarChart3,
  Users,
  GraduationCap,
  Table2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Search,
  Gauge,
  Building2,
  User,
  FolderKanban,
  X,
} from 'lucide-react'

import { cn } from '@/lib/utils'
import { preloadRoute } from '@/lib/route-preload'
import deptLogo from '@/assets/logo-dept.svg'
import hexawareLogo from '@/assets/Blue Logo.png'

const navGroups = [
  {
    label: 'Overview',
    items: [
      { to: '/', label: 'Home', icon: Home },
      { to: '/hr-portal', label: 'HR Home', icon: Building2 },
      { to: '/hr-analytics', label: 'HR Analytics', icon: BarChart3 },
    ],
  },
  {
    label: 'Workforce',
    items: [
      { to: '/workforce', label: 'Workforce', icon: Users },
      { to: '/skills-experience', label: 'Skills & Experience', icon: GraduationCap },
      { to: '/employee-directory', label: 'Employee Directory', icon: Table2 },
    ],
  },
  {
    label: 'Utilization',
    items: [
      { to: '/utilization', label: 'Utilization Home', icon: Clock },
      { to: '/utilization/search', label: 'Search', icon: Search },
      { to: '/utilization/employees', label: 'Employee Utilization', icon: User },
      { to: '/utilization/projects', label: 'Project Utilization', icon: FolderKanban },
      { to: '/utilization/overview-summary', label: 'Utilization Overview', icon: Gauge },
    ],
  },
]

export function Sidebar({
  mobileOpen = false,
  onMobileClose,
}: {
  mobileOpen?: boolean
  onMobileClose?: () => void
}) {
  const [collapsed, setCollapsed] = React.useState(false)

  return (
    <>
      {/* Mobile backdrop overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          'flex h-screen shrink-0 flex-col border-r border-[#535983]/40 bg-[#07125E] text-white transition-[width] duration-200',
          // Desktop: normal flow, width toggles
          'lg:relative lg:z-auto lg:translate-x-0',
          collapsed ? 'lg:w-16' : 'lg:w-64',
          // Mobile: fixed off-canvas drawer, slides in
          'fixed inset-y-0 left-0 z-50 w-64 transition-transform duration-200 ease-out',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 flex-col justify-center gap-1 border-b border-[#535983]/40 px-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {/* DEPT is the foregrounded/primary mark (larger, first);
                  Hexaware renders smaller as a "powered by" secondary credit.
                  Rendered once — no duplicate responsive-breakpoint copies. */}
              <img src={deptLogo} alt="DEPT" className="h-7 w-auto shrink-0 brightness-0 invert" />
              {!collapsed && (
                <>
                  <span className="h-5 w-px bg-white/30" />
                  <img src={hexawareLogo} alt="Hexaware" className="h-5 w-auto shrink-0 opacity-80" />
                </>
              )}
            </div>
            <button
              type="button"
              onClick={onMobileClose}
              className="rounded-lg p-1.5 text-white/70 hover:bg-white/10 hover:text-white lg:hidden"
              aria-label="Close menu"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          {!collapsed && (
            <span className="truncate text-[11px] text-white/60">Workforce Analytics</span>
          )}
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto p-3">
          {navGroups.map((group) => (
            <div key={group.label}>
              {!collapsed && (
                <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-wider text-white/50">
                  {group.label}
                </p>
              )}
              <div className="space-y-1">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end
                    onClick={onMobileClose}
                    onMouseEnter={() => preloadRoute(item.to)}
                    onFocus={() => preloadRoute(item.to)}
                    onTouchStart={() => preloadRoute(item.to)}
                    className={({ isActive }) =>
                      cn(
                        'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-[#1D86FF]/15 text-[#1D86FF]'
                          : 'text-white/70 hover:bg-white/10 hover:text-white',
                      )
                    }
                    title={collapsed ? item.label : undefined}
                  >
                    {({ isActive }) => (
                      <>
                        <span
                          className={cn(
                            'absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-[#1D86FF] transition-opacity',
                            isActive ? 'opacity-100' : 'opacity-0',
                          )}
                        />
                        <item.icon className="h-4 w-4 shrink-0" />
                        {!collapsed && <span className="truncate">{item.label}</span>}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="hidden border-t border-[#535983]/40 p-3 lg:block">
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            className="flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm text-white/70 transition-colors hover:bg-white/10 hover:text-white"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>
    </>
  )
}
