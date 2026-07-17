import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, LogOut } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth-context'
import { apiClient } from '@/lib/api-client'
import deptLogo from '@/assets/dept-logo-cropped.png'
import hexawareLogo from '@/assets/Blue Logo.png'
// Note: frontend/src/assets/hero.png exists but is a purple/violet abstract
// graphic that clashes with this app's blue `--primary` brand system used
// everywhere else (sidebar, topbar, login page). Per the dashboard-design
// guidance to only use it "if it looks usable" / "fits cleanly", it's
// intentionally not used here — the wave/gradient treatment reused from
// login-page.tsx carries the visual instead.

/**
 * One-time full-screen landing page shown right after login, before the
 * user reaches the real dashboard (Home). Deliberately NOT wrapped in
 * AppLayout — no sidebar/topbar chrome here, matching the login page's
 * full-bleed treatment. Same gradient/brand system as login-page.tsx so it
 * reads as part of the same product rather than a different visual style.
 */
export function WelcomePage() {
  const navigate = useNavigate()
  const { setAuth } = useAuth()

  // AuthUser only carries `id` / `email` / `role` — no display-name field —
  // so there is nothing meaningful to greet the person by. Skip the
  // personalized pill entirely rather than showing a placeholder or the
  // raw email in a "Welcome, ..." pill.
  const displayName: string | null = null

  const handleSignOut = async () => {
    try {
      await apiClient.post('/auth/logout')
    } finally {
      setAuth(null)
      navigate('/login', { replace: true })
    }
  }

  return (
    // Same gradient anchored to `--primary` as login-page.tsx, for visual
    // continuity between the two full-screen (non-AppLayout) surfaces.
    <div className="relative flex min-h-screen w-full flex-col overflow-hidden bg-[linear-gradient(160deg,hsl(215,45%,95%)_0%,hsl(217,60%,82%)_50%,hsl(215,70%,38%)_100%)] dark:bg-[linear-gradient(160deg,#080F38_0%,#0B1866_50%,#1C4F97_100%)]">
      {/* wave-shaped accent at bottom of viewport, matching login page */}
      <svg
        className="pointer-events-none absolute bottom-0 left-0 h-[42vh] w-full"
        viewBox="0 0 1440 400"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          d="M0,160 C240,260 480,60 720,110 C960,160 1200,300 1440,200 L1440,400 L0,400 Z"
          fill="hsl(215 65% 42% / 0.38)"
          className="dark:opacity-50"
        />
        <path
          d="M0,220 C260,300 520,140 760,180 C1000,220 1220,340 1440,260 L1440,400 L0,400 Z"
          fill="hsl(215 70% 38% / 0.55)"
          className="dark:opacity-65"
        />
      </svg>

      {/* Top bar: brand logo lockup (same treatment as login-page.tsx) + sign out.
          `dept-logo-cropped.png` has its baked-in transparent margin trimmed
          to the glyph's actual bounding box, so it's now tightly cropped
          like the Hexaware PNG — equal `h-*` values read as equal visual
          weight instead of needing a compensating size ratio. */}
      <header className="relative z-10 flex items-center justify-between px-6 py-6 sm:px-10">
        <div className="flex items-center gap-4 py-1 sm:gap-5">
          <img
            src={deptLogo}
            alt="DEPT"
            className="h-7 w-auto shrink-0 object-contain dark:invert sm:h-8"
          />
          <span className="h-6 w-px shrink-0 bg-border/70 sm:h-7" />
          <img
            src={hexawareLogo}
            alt="Hexaware"
            className="h-6 w-auto shrink-0 object-contain sm:h-7"
          />
        </div>
        <Button variant="outline" size="sm" onClick={handleSignOut} className="bg-card/70 backdrop-blur">
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </header>

      {/* Hero */}
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 py-10 text-center sm:px-10">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
          className="flex max-w-2xl flex-col items-center"
        >
          {displayName && (
            <div className="mb-5 inline-flex items-center rounded-full bg-card/80 px-4 py-1.5 text-sm font-semibold text-primary shadow-sm backdrop-blur">
              Welcome, {displayName}
            </div>
          )}

          <h1 className="mb-4 text-[32px] font-extrabold leading-tight tracking-tight text-foreground sm:text-[44px]">
            Your Workforce, At a Glance
          </h1>
          <p className="mb-8 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Real-time headcount, utilization, and deployment insights for DEPT | Hexaware.
          </p>

          <Button size="lg" className="h-12 px-8 text-[15px] font-bold" onClick={() => navigate('/')}>
            Enter Dashboard
            <ArrowRight className="h-4 w-4" />
          </Button>
        </motion.div>
      </main>
    </div>
  )
}
