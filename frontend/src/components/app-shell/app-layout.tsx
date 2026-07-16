import * as React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'

import { Sidebar } from './sidebar'
import { Topbar } from './topbar'
import { StatusFooter } from './status-footer'

const pageTitles: Record<string, string> = {
  '/': 'Home',
  '/hr-analytics': 'HR Analytics',
  '/workforce': 'Workforce',
  '/skills-experience': 'Skills & Experience',
  '/employee-directory': 'Employee Directory',
}

export function AppLayout() {
  const location = useLocation()
  const title = pageTitles[location.pathname] ?? 'Workforce Analytics'
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false)

  // Close the drawer whenever the route changes.
  React.useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar mobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar
          title={title}
          variant={location.pathname === '/' ? 'home' : 'default'}
          onMenuClick={() => setMobileNavOpen(true)}
        />
        <main className="flex-1 overflow-y-auto overflow-x-hidden bg-background p-4 sm:p-6 lg:p-8">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
        <StatusFooter />
      </div>
    </div>
  )
}
