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
const HomePage = React.lazy(() => import('@/pages/home-page').then((m) => ({ default: m.HomePage })))
const HrPortalHomePage = React.lazy(() =>
  import('@/pages/hr-portal-home-page').then((m) => ({ default: m.HrPortalHomePage })),
)
const HrAnalyticsPage = React.lazy(() =>
  import('@/pages/hr-analytics-page').then((m) => ({ default: m.HrAnalyticsPage })),
)
const WorkforcePage = React.lazy(() =>
  import('@/pages/workforce-page').then((m) => ({ default: m.WorkforcePage })),
)
const SkillsExperiencePage = React.lazy(() =>
  import('@/pages/skills-experience-page').then((m) => ({ default: m.SkillsExperiencePage })),
)
const EmployeeDirectoryPage = React.lazy(() =>
  import('@/pages/employee-directory-page').then((m) => ({ default: m.EmployeeDirectoryPage })),
)
const UtilizationHomePage = React.lazy(() =>
  import('@/pages/utilization-home-page').then((m) => ({ default: m.UtilizationHomePage })),
)
const UtilizationSearchPage = React.lazy(() =>
  import('@/pages/utilization-search-page').then((m) => ({ default: m.UtilizationSearchPage })),
)
const UtilizationResultsPage = React.lazy(() =>
  import('@/pages/utilization-results-page').then((m) => ({ default: m.UtilizationResultsPage })),
)
const EmployeeUtilizationPage = React.lazy(() =>
  import('@/pages/employee-utilization-page').then((m) => ({ default: m.EmployeeUtilizationPage })),
)
const ProjectUtilizationPage = React.lazy(() =>
  import('@/pages/project-utilization-page').then((m) => ({ default: m.ProjectUtilizationPage })),
)
const UtilizationOverviewPage = React.lazy(() =>
  import('@/pages/utilization-overview-page').then((m) => ({ default: m.UtilizationOverviewPage })),
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
