import * as React from 'react'
import { AlertTriangle } from 'lucide-react'

import { Button } from '@/components/ui/button'

interface Props {
  children: React.ReactNode
}

interface State {
  error: Error | null
}

/**
 * Catches render crashes in whatever page is mounted inside AppLayout's
 * <Outlet>, so a bug in one page (e.g. an unguarded null field from a
 * known data-quality issue) shows a recoverable error card instead of
 * blanking the entire app — sidebar/topbar stay usable so the user can
 * navigate elsewhere. AppLayout remounts this with `key={pathname}`, so
 * navigating away from the crashed route clears the error automatically.
 */
export class RouteErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Route crashed:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-border bg-card p-12 text-center shadow-card">
          <AlertTriangle className="h-10 w-10 text-destructive" />
          <h2 className="text-lg font-semibold">This page couldn't load</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            Something went wrong rendering this page. Try reloading — if it keeps happening, the
            data behind this screen may need attention.
          </p>
          <Button variant="outline" onClick={() => window.location.reload()}>
            Reload page
          </Button>
        </div>
      )
    }
    return this.props.children
  }
}
