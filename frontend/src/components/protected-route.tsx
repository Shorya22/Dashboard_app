import * as React from 'react'
import { Navigate } from 'react-router-dom'
import axios from 'axios'

import { useAuth } from '@/lib/auth-context'
import { authTokenStore } from '@/lib/auth-context'

/**
 * Gate for any authenticated screen. If no access token is in memory
 * (e.g. after a hard refresh, which clears all React state), it attempts
 * one silent POST /api/auth/refresh — the httpOnly refresh cookie from a
 * previous login may still be valid — before giving up and redirecting
 * to /login.
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { accessToken, setAuth, isInitializing, setIsInitializing } = useAuth()
  const [checked, setChecked] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false

    async function attemptSilentRefresh() {
      if (authTokenStore.token) {
        if (!cancelled) {
          setChecked(true)
          setIsInitializing(false)
        }
        return
      }
      try {
        const res = await axios.post('/api/auth/refresh', null, {
          withCredentials: true,
        })
        if (!cancelled) {
          setAuth(res.data.access_token as string)
        }
      } catch {
        if (!cancelled) {
          setAuth(null)
        }
      } finally {
        if (!cancelled) {
          setChecked(true)
          setIsInitializing(false)
        }
      }
    }

    void attemptSilentRefresh()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!checked || isInitializing) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!accessToken) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
