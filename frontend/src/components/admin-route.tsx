import * as React from 'react'
import { Navigate } from 'react-router-dom'

import { useAuth } from '@/lib/auth-context'

/**
 * Gate for admin-only screens, layered on top of ProtectedRoute (which
 * has already guaranteed an access token). The user profile (with the
 * role) is fetched asynchronously by AuthBridge, so while it's still
 * loading we show a spinner rather than briefly redirecting an admin
 * away. Non-admins are sent to the dashboard home.
 */
export function AdminRoute({ children }: { children: React.ReactNode }) {
  const { accessToken, user } = useAuth()

  // Token present but profile not fetched yet — wait.
  if (accessToken && !user) {
    return (
      <div className="flex h-full w-full items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
