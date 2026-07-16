import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, User, LogOut, Bell, Menu } from 'lucide-react'

import { cn } from '@/lib/utils'
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
  subtitle,
  variant = 'default',
  onMenuClick,
}: {
  title: string
  subtitle?: string
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
    <div className="flex items-center gap-2 sm:gap-5">
      {/* Mobile: icon-only search trigger to avoid overflowing narrow topbars */}
      <button
        type="button"
        onClick={() => setCommandOpen(true)}
        aria-label="Search"
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[#DCE7F5] bg-white text-slate-500 shadow-sm shadow-slate-900/5 transition hover:shadow-md sm:hidden"
      >
        <Search className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => setCommandOpen(true)}
        className="hidden h-9 w-[220px] items-center justify-between rounded-full border border-[#DCE7F5] bg-white px-4 text-slate-900 shadow-sm shadow-slate-900/5 transition hover:shadow-md sm:flex md:w-[320px]"
      >
        <span className="flex items-center gap-3 text-sm font-medium text-slate-500">
          <Search className="h-4 w-4" />
          Search...
        </span>
        <kbd className="rounded-full border border-[#E5E7EB] bg-[#F3F4F6] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
          ⌘K
        </kbd>
      </button>

      <button
        type="button"
        aria-label="Notifications"
        className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-slate-700 transition hover:bg-[#EEF2FF]"
      >
        <Bell className="h-5 w-5" />
        <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-violet-500 ring-2 ring-white" />
      </button>

      <div className="hidden h-8 w-px bg-[#E5E7EB] sm:block" />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label="Open account menu"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-slate-900 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-200 sm:h-12 sm:w-12"
          >
            <User className="h-5 w-5" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>Account</DropdownMenuLabel>
          <div className="px-3 py-2 text-sm text-slate-700">{user?.email ?? 'Not signed in'}</div>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-sm px-2 py-2 text-sm"
              onClick={handleLogout}
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
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
          ? 'text-slate-700 hover:bg-slate-100'
          : 'text-muted-foreground hover:bg-muted',
      )}
    >
      <Menu className="h-5 w-5" />
    </button>
  )

  if (variant === 'home') {
    return (
      <header className="flex shrink-0 flex-col border-b border-[#D7E4FF] bg-[#F3F7FF]/90 backdrop-blur">
        <div className="h-1 w-full bg-[#4C82FF]" />
        <div className="flex h-14 items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            {menuButton}
            <div>
              <p className="truncate text-base font-semibold tracking-tight text-[#112A60] sm:text-lg">
                {title}
              </p>
              {subtitle ? (
                <p className="text-xs text-[#5D6F99]">{subtitle}</p>
              ) : null}
            </div>
          </div>
          {controls}
        </div>
      </header>
    )
  }

  return (
    <header className="flex shrink-0 flex-col border-b border-[#D7E4FF] bg-[#F3F7FF]/90 backdrop-blur">
      <div className="h-1 w-full bg-[#4C82FF]" />
      <div className="flex h-14 items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          {menuButton}
          <div>
            <p className="truncate text-base font-semibold tracking-tight text-[#112A60] sm:text-lg">
              {title}
            </p>
            <p className="text-xs text-[#5D6F99]">
              {subtitle ?? 'Dashboard overview and quick actions'}
            </p>
          </div>
        </div>
        {controls}
      </div>
    </header>
  )
}
