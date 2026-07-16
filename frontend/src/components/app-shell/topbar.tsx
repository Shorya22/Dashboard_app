import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, User, LogOut, Bell, Menu } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { CommandMenu } from './command-menu'
import { useAuth } from '@/lib/auth-context'
import { apiClient } from '@/lib/api-client'

export function Topbar({
  title,
  variant = 'default',
  onMenuClick,
}: {
  title: string
  /**
   * 'home' renders the reference PDF's distinctive full-width DEPT|HEXAWARE
   * banner (navy bar + primary-blue tagline bar) instead of the standard topbar
   * title. This is Home-route-only per the design gap fix — every other
   * route keeps the standard topbar. Functional controls (search,
   * notifications, user menu) stay identical in both variants.
   */
  variant?: 'default' | 'home'
  /** Opens the mobile sidebar drawer. Hamburger button only renders below lg. */
  onMenuClick?: () => void
}) {
  const [commandOpen, setCommandOpen] = React.useState(false)
  const navigate = useNavigate()
  const { user, setAuth } = useAuth()

  React.useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCommandOpen((v) => !v)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleLogout = async () => {
    try {
      await apiClient.post('/auth/logout')
    } finally {
      setAuth(null)
      navigate('/login', { replace: true })
    }
  }

  const controls = (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        className={
          variant === 'home'
            ? 'gap-2 border-white/30 bg-white/10 text-white hover:bg-white/20 hover:text-white'
            : 'gap-2 text-muted-foreground'
        }
        onClick={() => setCommandOpen(true)}
      >
        <Search className="h-4 w-4" />
        <span className="hidden sm:inline">Search...</span>
        <kbd
          className={
            variant === 'home'
              ? 'hidden rounded border border-white/30 bg-white/10 px-1.5 py-0.5 text-[10px] sm:inline'
              : 'hidden rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] sm:inline'
          }
        >
          ⌘K
        </kbd>
      </Button>

      <Button
        variant="ghost"
        size="icon"
        aria-label="Notifications"
        className={
          variant === 'home'
            ? 'relative text-white hover:bg-white/20 hover:text-white'
            : 'relative text-muted-foreground'
        }
      >
        <Bell className="h-4 w-4" />
        <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-primary" />
      </Button>

      <div className={variant === 'home' ? 'mx-1 h-6 w-px bg-white/30' : 'mx-1 h-6 w-px bg-border'} />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="User menu"
            className={
              variant === 'home'
                ? 'rounded-full bg-white/15 text-white hover:bg-white/25'
                : 'rounded-full bg-primary/10 text-primary hover:bg-primary/20'
            }
          >
            <User className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>{user?.email ?? 'Account'}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={handleLogout} className="gap-2">
            <LogOut className="h-4 w-4" />
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <CommandMenu open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  )

  const menuButton = onMenuClick && (
    <button
      type="button"
      onClick={onMenuClick}
      aria-label="Open menu"
      className={cn(
        'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg lg:hidden',
        variant === 'home'
          ? 'text-white hover:bg-white/20'
          : 'text-muted-foreground hover:bg-muted',
      )}
    >
      <Menu className="h-5 w-5" />
    </button>
  )

  if (variant === 'home') {
    return (
      <header className="flex shrink-0 flex-col">
        {/* Logo lockup intentionally omitted here — the sidebar already
            renders the DEPT | Hexaware branding once per screen, so this
            home-variant bar keeps only the tagline/actions row. */}
        <div className="flex items-center justify-between gap-2 bg-[#040D43] px-3 py-3 sm:gap-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            {menuButton}
            <span className="truncate text-base font-semibold tracking-tight text-white sm:text-lg">
              {title}
            </span>
          </div>
          {controls}
        </div>
        <div className="flex h-9 w-full items-center justify-center bg-primary px-3 sm:px-6">
          <p className="truncate text-[11px] font-medium tracking-wide text-white sm:text-sm">
            Connected People. Smarter Delivery Decisions.
          </p>
        </div>
      </header>
    )
  }

  return (
    <header className="flex shrink-0 flex-col border-b border-border bg-card/80 backdrop-blur">
      <div className="h-1 w-full bg-primary" />
      <div className="flex h-[60px] items-center justify-between gap-2 px-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-2">
          {menuButton}
          <h1 className="truncate text-base font-semibold tracking-tight sm:text-lg">{title}</h1>
        </div>
        {controls}
      </div>
    </header>
  )
}
