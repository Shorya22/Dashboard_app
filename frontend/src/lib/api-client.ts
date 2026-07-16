import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { authTokenStore } from './auth-context'

// Fired when a silent refresh fails so app-level code (outside the axios
// module) can redirect to /login. Kept as a simple callback instead of a
// hard import of react-router to avoid a circular dependency.
let onAuthLost: (() => void) | null = null
export function setOnAuthLost(cb: () => void) {
  onAuthLost = cb
}

// Also let app code update the in-memory token after a successful silent
// refresh (e.g. on initial app load before AuthProvider mounts a setter).
let onTokenRefreshed: ((token: string) => void) | null = null
export function setOnTokenRefreshed(cb: (token: string) => void) {
  onTokenRefreshed = cb
}

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const apiClient = axios.create({
  baseURL,
  withCredentials: true, // send the httpOnly refresh cookie
})

apiClient.interceptors.request.use((config) => {
  if (authTokenStore.token) {
    config.headers.set('Authorization', `Bearer ${authTokenStore.token}`)
  }
  return config
})

let refreshPromise: Promise<string | null> | null = null

async function performSilentRefresh(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = axios
      .post('/api/auth/refresh', null, { withCredentials: true })
      .then((res) => {
        const token = res.data.access_token as string
        authTokenStore.token = token
        onTokenRefreshed?.(token)
        return token
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      originalRequest._retry = true
      const newToken = await performSilentRefresh()
      if (newToken) {
        originalRequest.headers.set('Authorization', `Bearer ${newToken}`)
        return apiClient(originalRequest)
      }
      authTokenStore.token = null
      onAuthLost?.()
    }

    return Promise.reject(error)
  },
)

export function extractErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return fallback
}
