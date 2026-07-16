import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      // Data is Excel-backed and refreshed at most a few times a session
      // (per data-model skill), so treat it as fresh for 5 minutes instead
      // of React Query's default 0 / this app's prior 30s — cuts needless
      // refetches every time a user navigates back to a page they already
      // visited, without risking stale data within a session.
      staleTime: 5 * 60_000,
    },
  },
})
