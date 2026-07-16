import * as React from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Routes, Route, useNavigate } from 'react-router-dom'

import { queryClient } from '@/lib/query-client'
import { AuthProvider, useAuth } from '@/lib/auth-context'
import { apiClient, setOnAuthLost, setOnTokenRefreshed } from '@/lib/api-client'
import { ProtectedRoute } from '@/components/protected-route'
import { AppLayout } from '@/components/app-shell/app-layout'
import { LoginPage } from '@/pages/login-page'
import { HomePage } from '@/pages/home-page'
import { HrPortalHomePage } from '@/pages/hr-portal-home-page'
import { HrAnalyticsPage } from '@/pages/hr-analytics-page'
import { WorkforcePage } from '@/pages/workforce-page'
import { SkillsExperiencePage } from '@/pages/skills-experience-page'
import { EmployeeDirectoryPage } from '@/pages/employee-directory-page'
import { UtilizationHomePage } from '@/pages/utilization-home-page'
import { UtilizationSearchPage } from '@/pages/utilization-search-page'
import { UtilizationResultsPage } from '@/pages/utilization-results-page'
import { EmployeeUtilizationPage } from '@/pages/employee-utilization-page'
import { ProjectUtilizationPage } from '@/pages/project-utilization-page'
import { UtilizationOverviewPage } from '@/pages/utilization-overview-page'

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
        <Route index element={<HomePage />} />
        <Route path="hr-portal" element={<HrPortalHomePage />} />
        <Route path="hr-analytics" element={<HrAnalyticsPage />} />
        <Route path="workforce" element={<WorkforcePage />} />
        <Route path="skills-experience" element={<SkillsExperiencePage />} />
        <Route path="employee-directory" element={<EmployeeDirectoryPage />} />
        <Route path="utilization" element={<UtilizationHomePage />} />
        <Route path="utilization/search" element={<UtilizationSearchPage />} />
        <Route path="utilization/results" element={<UtilizationResultsPage />} />
        <Route path="utilization/employees" element={<EmployeeUtilizationPage />} />
        <Route path="utilization/employees/:employee" element={<EmployeeUtilizationPage />} />
        <Route path="utilization/projects" element={<ProjectUtilizationPage />} />
        <Route path="utilization/projects/:holding" element={<ProjectUtilizationPage />} />
        <Route path="utilization/overview-summary" element={<UtilizationOverviewPage />} />
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
