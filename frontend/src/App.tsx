import * as React from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Routes, Route, useNavigate } from 'react-router-dom'

import { queryClient } from '@/lib/query-client'
import { AuthProvider, useAuth } from '@/lib/auth-context'
import { apiClient, setOnAuthLost, setOnTokenRefreshed } from '@/lib/api-client'
import { ProtectedRoute } from '@/components/protected-route'
import { AppLayout } from '@/components/app-shell/app-layout'
import { PageLoadingFallback } from '@/components/dashboard/page-loading-fallback'

// Route-level code splitting: each page's JS is only fetched when the user
// actually navigates there, instead of shipping all 15+ pages in one
// eagerly-loaded bundle. LoginPage stays eager since it's the first thing
// an unauthenticated user sees.
import { LoginPage } from '@/pages/login-page'
// Route chunk importers are centralized in route-preload.ts so the sidebar
// can kick off the same dynamic import() on link hover/focus, well before
// the click — see that file for why.
import { routeImporters, preloadRoute } from '@/lib/route-preload'
const HomePage = React.lazy(() =>
  routeImporters['/']().then((m) => ({ default: (m as typeof import('@/pages/home-page')).HomePage })),
)
const HrPortalHomePage = React.lazy(() =>
  routeImporters['/hr-portal']().then((m) => ({
    default: (m as typeof import('@/pages/hr-portal-home-page')).HrPortalHomePage,
  })),
)
const HrAnalyticsPage = React.lazy(() =>
  routeImporters['/hr-analytics']().then((m) => ({
    default: (m as typeof import('@/pages/hr-analytics-page')).HrAnalyticsPage,
  })),
)
const WorkforcePage = React.lazy(() =>
  routeImporters['/workforce']().then((m) => ({
    default: (m as typeof import('@/pages/workforce-page')).WorkforcePage,
  })),
)
const SkillsExperiencePage = React.lazy(() =>
  routeImporters['/skills-experience']().then((m) => ({
    default: (m as typeof import('@/pages/skills-experience-page')).SkillsExperiencePage,
  })),
)
const EmployeeDirectoryPage = React.lazy(() =>
  routeImporters['/employee-directory']().then((m) => ({
    default: (m as typeof import('@/pages/employee-directory-page')).EmployeeDirectoryPage,
  })),
)
const UtilizationHomePage = React.lazy(() =>
  routeImporters['/utilization']().then((m) => ({
    default: (m as typeof import('@/pages/utilization-home-page')).UtilizationHomePage,
  })),
)
const UtilizationSearchPage = React.lazy(() =>
  routeImporters['/utilization/search']().then((m) => ({
    default: (m as typeof import('@/pages/utilization-search-page')).UtilizationSearchPage,
  })),
)
const UtilizationResultsPage = React.lazy(() =>
  import('@/pages/utilization-results-page').then((m) => ({ default: m.UtilizationResultsPage })),
)
const EmployeeUtilizationPage = React.lazy(() =>
  routeImporters['/utilization/employees']().then((m) => ({
    default: (m as typeof import('@/pages/employee-utilization-page')).EmployeeUtilizationPage,
  })),
)
const ProjectUtilizationPage = React.lazy(() =>
  routeImporters['/utilization/projects']().then((m) => ({
    default: (m as typeof import('@/pages/project-utilization-page')).ProjectUtilizationPage,
  })),
)
const UtilizationOverviewPage = React.lazy(() =>
  routeImporters['/utilization/overview-summary']().then((m) => ({
    default: (m as typeof import('@/pages/utilization-overview-page')).UtilizationOverviewPage,
  })),
)

function AuthBridge() {
  const { accessToken, user, setAuth } = useAuth()
  const navigate = useNavigate()

  React.useEffect(() => {
    // Let the axios interceptor (outside React) push a refreshed token
    // into context, and redirect to /login when a silent refresh fails
    // during an in-flight authenticated request.
    setOnTokenRefreshed((token) => setAuth(token))
    setOnAuthLost(() => {
      setAuth(null)
      navigate('/login', { replace: true })
    })
  }, [setAuth, navigate])

  // Once we have an access token but no user profile yet (fresh login or
  // post-refresh), fetch it once for display in the topbar.
  React.useEffect(() => {
    if (!accessToken || user) return
    let cancelled = false
    apiClient
      .get('/auth/me')
      .then((res) => {
        if (!cancelled) setAuth(accessToken, res.data)
      })
      .catch(() => {
        /* non-fatal — topbar just shows a generic label */
      })
    return () => {
      cancelled = true
    }
  }, [accessToken, user, setAuth])

  // Once authenticated, warm the chunk cache for the handful of pages users
  // visit most (Home is eager-adjacent already; Workforce and Skills &
  // Experience are the heaviest client-side-aggregation pages, and clicking
  // into them cold is where the "stuck" feeling was most visible). Runs at
  // browser idle time so it never competes with the current page's own
  // data/render work.
  React.useEffect(() => {
    if (!accessToken) return
    const idle =
      'requestIdleCallback' in window
        ? window.requestIdleCallback
        : (cb: () => void) => window.setTimeout(cb, 1)
    const handle = idle(() => {
      void preloadRoute('/workforce')
      void preloadRoute('/skills-experience')
    })
    return () => {
      if ('cancelIdleCallback' in window && typeof handle === 'number') {
        window.cancelIdleCallback(handle)
      }
    }
  }, [accessToken])

  return null
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route
          index
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <HomePage />
            </React.Suspense>
          }
        />
        <Route
          path="hr-portal"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <HrPortalHomePage />
            </React.Suspense>
          }
        />
        <Route
          path="hr-analytics"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <HrAnalyticsPage />
            </React.Suspense>
          }
        />
        <Route
          path="workforce"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <WorkforcePage />
            </React.Suspense>
          }
        />
        <Route
          path="skills-experience"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <SkillsExperiencePage />
            </React.Suspense>
          }
        />
        <Route
          path="employee-directory"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <EmployeeDirectoryPage />
            </React.Suspense>
          }
        />
        <Route
          path="utilization"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <UtilizationHomePage />
            </React.Suspense>
          }
        />
        <Route
          path="utilization/search"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <UtilizationSearchPage />
            </React.Suspense>
          }
        />
        <Route
          path="utilization/results"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <UtilizationResultsPage />
            </React.Suspense>
          }
        />
        <Route
          path="utilization/employees"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <EmployeeUtilizationPage />
            </React.Suspense>
          }
        />
        <Route
          path="utilization/employees/:employee"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <EmployeeUtilizationPage />
            </React.Suspense>
          }
        />
        <Route
          path="utilization/projects"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <ProjectUtilizationPage />
            </React.Suspense>
          }
        />
        <Route
          path="utilization/projects/:holding"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <ProjectUtilizationPage />
            </React.Suspense>
          }
        />
        <Route
          path="utilization/overview-summary"
          element={
            <React.Suspense fallback={<PageLoadingFallback />}>
              <UtilizationOverviewPage />
            </React.Suspense>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AuthBridge />
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
