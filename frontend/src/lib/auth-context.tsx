import * as React from 'react'

interface AuthUser {
  id?: string
  email?: string
  role?: string
}

interface AuthContextValue {
  accessToken: string | null
  user: AuthUser | null
  setAuth: (token: string | null, user?: AuthUser | null) => void
  isInitializing: boolean
  setIsInitializing: (v: boolean) => void
}

// Access token lives only in memory (React state) — never localStorage —
// so an XSS payload can't read a persisted token. The refresh token is an
// httpOnly cookie the browser manages; JS never touches it directly.
const AuthContext = React.createContext<AuthContextValue | undefined>(
  undefined,
)

// Module-level mirror so the axios interceptor (outside React) can read the
// current token/set it after a silent refresh without needing hooks.
export const authTokenStore: { token: string | null } = { token: null }

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = React.useState<string | null>(null)
  const [user, setUser] = React.useState<AuthUser | null>(null)
  const [isInitializing, setIsInitializing] = React.useState(true)

  const setAuth = React.useCallback(
    (token: string | null, nextUser?: AuthUser | null) => {
      authTokenStore.token = token
      setAccessToken(token)
      if (nextUser !== undefined) setUser(nextUser)
      if (token === null) setUser(null)
    },
    [],
  )

  const value = React.useMemo(
    () => ({ accessToken, user, setAuth, isInitializing, setIsInitializing }),
    [accessToken, user, setAuth, isInitializing],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = React.useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
