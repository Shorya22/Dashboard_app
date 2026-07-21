import * as React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'

import { Sidebar } from './sidebar'
import { Topbar } from './topbar'
import { RouteErrorBoundary } from './route-error-boundary'
import { installGlobalTooltipDismissal } from '@/lib/chart-tooltip-touch-store'

const pageTitles: Record<string, string> = {
  '/': 'Home',
  '/hr-portal': 'HR Portal',
  '/hr-analytics': 'HR Analytics',
  '/workforce': 'Workforce',
  '/skills-experience': 'Skills & Experience',
  '/employee-directory': 'Employee Directory',
  '/utilization': 'Utilization',
  '/utilization/search': 'Search Utilization',
  '/utilization/employees': 'Employee Utilization',
  '/utilization/projects': 'Project Utilization',
  '/utilization/overview-summary': 'Utilization Overview',
  '/settings': 'Settings',
}

const pageSubtitles: Record<string, string> = {
  '/': 'Workforce overview at a glance',
  '/hr-portal': 'Workforce composition overview — status, region, entity, and experience',
  '/hr-analytics': 'Headcount, exits, and attrition',
  '/workforce': 'Seniority, type, and regional distribution',
  '/skills-experience': 'Skills and experience breakdown across workforce segments',
  '/employee-directory': 'Browse employees and their current roles',
  '/utilization': 'Weekly time booking across client and internal work',
  '/utilization/search': 'Filter time-booking records by week, region, department, entity, holding, or hours type',
  '/utilization/employees': 'Review employee utilization detail',
  '/utilization/projects': 'Review project utilization detail',
  '/utilization/overview-summary': 'Period utilization rate and employee-level breakdown',
  '/settings': 'Customize chart colors and other app preferences',
}

export function AppLayout() {
  const location = useLocation()
  const title =
    pageTitles[location.pathname] ||
    (location.pathname.startsWith('/utilization/employees/') ? 'Employee Utilization' :
    location.pathname.startsWith('/utilization/projects/') ? 'Project Utilization' :
    'Overview')
  const subtitle =
    pageSubtitles[location.pathname] ||
    (location.pathname.startsWith('/utilization/employees/') ? 'Review employee utilization detail' :
    location.pathname.startsWith('/utilization/projects/') ? 'Review project utilization detail' :
    'Dashboard overview and quick actions')
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false)

  // Close the drawer whenever the route changes.
  React.useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname])

  // Scroll/touch-drag/tap-outside chart-tooltip dismissal — see
  // chart-tooltip-touch-store.ts. One-time, app-wide; idempotent if this
  // ever mounts more than once.
  React.useEffect(() => {
    installGlobalTooltipDismissal()
  }, [])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar mobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar
          title={title}
          subtitle={subtitle}
          variant={location.pathname === '/' ? 'home' : 'default'}
          onMenuClick={() => setMobileNavOpen(true)}
        />
        <main className="flex-1 overflow-y-auto overflow-x-hidden bg-background p-4 sm:p-5 lg:p-6">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
            >
              <RouteErrorBoundary key={location.pathname}>
                <Outlet />
              </RouteErrorBoundary>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
