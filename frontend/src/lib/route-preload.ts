// Single source of truth for each lazy-loaded page's dynamic import(), so
// App.tsx's React.lazy() and the sidebar's hover/focus prefetch both trigger
// the exact same chunk fetch (and share the browser's module cache — calling
// import() twice for the same specifier is a cache hit, not a double fetch).
//
// Why this exists: route-based code splitting means a page's JS chunk isn't
// fetched until the user navigates to it. On a slow connection that fetch
// can take long enough that clicking a sidebar link "feels stuck" for a
// beat before the Suspense fallback's first paint. Kicking the fetch off on
// hover/focus (well before the click) means the chunk is usually already in
// flight or cached by the time the user actually clicks.
export const routeImporters: Record<string, () => Promise<unknown>> = {
  '/welcome': () => import('@/pages/welcome-page'),
  '/': () => import('@/pages/home-page'),
  '/hr-portal': () => import('@/pages/hr-portal-home-page'),
  '/hr-analytics': () => import('@/pages/hr-analytics-page'),
  '/workforce': () => import('@/pages/workforce-page'),
  '/skills-experience': () => import('@/pages/skills-experience-page'),
  '/employee-directory': () => import('@/pages/employee-directory-page'),
  '/utilization': () => import('@/pages/utilization-home-page'),
  '/utilization/search': () => import('@/pages/utilization-search-page'),
  '/utilization/employees': () => import('@/pages/employee-utilization-page'),
  '/utilization/projects': () => import('@/pages/project-utilization-page'),
  '/utilization/overview-summary': () => import('@/pages/utilization-overview-page'),
  '/settings': () => import('@/pages/settings-page'),
}

const preloaded = new Set<string>()

/** Start fetching a route's JS chunk ahead of navigation (sidebar hover/focus).
 * Safe to call repeatedly — the underlying dynamic import() is cached by the
 * browser/bundler after the first call, and we also short-circuit locally. */
export function preloadRoute(to: string) {
  if (preloaded.has(to)) return
  const importer = routeImporters[to]
  if (!importer) return
  preloaded.add(to)
  importer().catch(() => {
    // Non-fatal: if the prefetch fails (e.g. offline), the normal
    // navigation Suspense fallback + React.lazy() retry the fetch anyway.
    preloaded.delete(to)
  })
}
