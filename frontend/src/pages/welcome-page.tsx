import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import {
  ArrowRight,
  BarChart3,
  Clock,
  FolderKanban,
  Globe,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Sparkles,
  TrendingUp,
  UserMinus,
  Users,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/auth-context'
import { apiClient } from '@/lib/api-client'
import { DashboardPreview } from '@/components/landing/dashboard-preview'
import { FeatureCard } from '@/components/landing/feature-card'
import deptLogo from '@/assets/dept-logo-cropped.png'
import hexawareLogo from '@/assets/Blue Logo.png'

// Every capability below maps to a real module in the cockpit (verified by
// touring the live app — see the sidebar: Workforce / HR Analytics / Skills
// & Experience / Utilization / Project Utilization). Descriptions use the
// product's own measure names (GCC vs non-GCC, voluntary/involuntary
// attrition, period utilization bands, skill bifurcation). Deliberately no
// "AI-powered" claim — the product has no AI features; "GCC" is a genuine
// dimension in this dataset, not marketing gloss.
const FEATURES = [
  {
    icon: BarChart3,
    title: 'Workforce Analytics',
    description:
      'Headcount, month-wise growth, and composition — GCC vs non-GCC, seniority, and grade mix in one view.',
  },
  {
    icon: UserMinus,
    title: 'HR & Attrition',
    description:
      'Joiners, exits, and monthly resignation trends, split across voluntary and involuntary attrition.',
  },
  {
    icon: Clock,
    title: 'Employee Utilization',
    description:
      'Client vs internal hours, weekly booking trends, and period utilization by high, moderate, and low band.',
  },
  {
    icon: GraduationCap,
    title: 'Skills & Experience',
    description:
      'Skills covered and experience bands, bifurcated by region, seniority, and years of experience.',
  },
  {
    icon: FolderKanban,
    title: 'Project Deployment',
    description:
      'Per-project and per-holding deployment, with drill-down into the underlying booking records.',
  },
  {
    icon: Globe,
    title: 'Global Delivery',
    description:
      'Region and market breakdowns spanning the AMER, EMEA, and APAC delivery footprint.',
  },
]

// Coverage strip — real dimensions the cockpit spans, no fabricated figures.
const DIMENSIONS = [
  { icon: Users, label: 'Workforce', sub: 'Headcount, growth & composition' },
  { icon: Clock, label: 'Utilization', sub: 'Client vs internal hours' },
  { icon: TrendingUp, label: 'Retention', sub: 'Joiners, exits & attrition' },
  { icon: Globe, label: 'Global', sub: 'AMER · EMEA · APAC' },
]

/** Nav link with an animated underline that grows on hover/focus — the
 * professional touch that a plain text link lacks. */
function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    document.getElementById(to)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  return (
    <a
      href={`#${to}`}
      onClick={handleClick}
      className="group relative rounded-sm text-[15px] font-medium text-foreground/70 transition-colors hover:text-foreground focus-visible:text-foreground focus-visible:outline-none"
    >
      {children}
      <span className="absolute -bottom-1 left-0 h-0.5 w-0 rounded-full bg-primary transition-all duration-300 group-hover:w-full group-focus-visible:w-full" />
    </a>
  )
}

/**
 * One-time full-screen landing page shown right after login, before the user
 * reaches the real dashboard (Home). Deliberately NOT wrapped in AppLayout —
 * no app sidebar/topbar; it has its own premium marketing chrome instead.
 *
 * Content is grounded in a walkthrough of the live cockpit, so the copy and
 * the preview reflect the product's real modules and measure names.
 *
 * Intentionally a committed LIGHT surface (no dark: variants): the dashboard,
 * both design references, and the brand palette are all light, and the app
 * has no dark-mode color palette defined (index.css only has a light :root),
 * so the semantic tokens used here resolve to the dashboard's exact colors
 * and never flip — keeping this page pixel-consistent with the dashboard it
 * leads into.
 */
export function WelcomePage() {
  const navigate = useNavigate()
  const { setAuth } = useAuth()
  const reduceMotion = useReducedMotion()

  // Navbar blends into the hero gradient at the top (transparent) and only
  // materializes into a glass bar once the user scrolls — so it reads as
  // part of the page, not a detached strip pinned above it.
  const [scrolled, setScrolled] = React.useState(false)
  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const handleSignOut = async () => {
    try {
      await apiClient.post('/auth/logout')
    } finally {
      setAuth(null)
      navigate('/login', { replace: true })
    }
  }

  const scrollToId = (id: string) => (e: React.MouseEvent) => {
    e.preventDefault()
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const floatAnim = reduceMotion ? undefined : { y: [0, -10, 0] }
  const floatTransition = reduceMotion
    ? undefined
    : { duration: 6, repeat: Infinity, ease: 'easeInOut' as const }

  return (
    <div className="relative min-h-screen w-full bg-[linear-gradient(180deg,#F8FAFC_0%,#EAF3FF_45%,#F8FAFC_100%)] text-foreground">
      {/* Decorative background: soft radial glows + faint dot texture. Clipped
          by this wrapper's own `overflow-hidden` (NOT the root's) so the glows
          that extend past the viewport don't add horizontal scroll — putting
          overflow on the root would break the navbar's `position: sticky`. */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div
          className="absolute -left-40 -top-40 h-[520px] w-[520px] rounded-full opacity-60 blur-3xl"
          style={{ background: 'radial-gradient(circle, hsl(215 80% 60% / 0.28), transparent 70%)' }}
        />
        <div
          className="absolute -right-32 top-24 h-[440px] w-[440px] rounded-full opacity-50 blur-3xl"
          style={{ background: 'radial-gradient(circle, hsl(217 90% 65% / 0.22), transparent 70%)' }}
        />
        <div
          className="absolute inset-0 opacity-[0.4]"
          style={{
            backgroundImage: 'radial-gradient(circle, hsl(215 40% 55% / 0.12) 1px, transparent 1px)',
            backgroundSize: '26px 26px',
          }}
        />
      </div>

      {/* Sticky navbar — transparent over the hero, glass once scrolled */}
      <header
        className={cn(
          'sticky top-0 z-50 transition-all duration-300',
          scrolled
            ? 'border-b border-border/60 bg-background/80 shadow-sm backdrop-blur-md'
            : 'border-b border-transparent bg-transparent',
        )}
      >
        <nav className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3.5 sm:px-8">
          <a
            href="#overview"
            onClick={scrollToId('overview')}
            className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 sm:gap-4"
            aria-label="DEPT and Hexaware GCC Cockpit — back to top"
          >
            <img src={deptLogo} alt="DEPT" className="h-6 w-auto shrink-0 object-contain sm:h-7" />
            <span className="h-5 w-px shrink-0 bg-border sm:h-6" />
            <img src={hexawareLogo} alt="Hexaware" className="h-5 w-auto shrink-0 object-contain sm:h-6" />
          </a>

          <div className="hidden items-center gap-9 md:flex">
            <NavLink to="overview">Overview</NavLink>
            <NavLink to="features">Capabilities</NavLink>
            <NavLink to="launch">Get Started</NavLink>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => navigate('/')}
              className="hidden shadow-sm shadow-primary/20 sm:inline-flex"
            >
              <LayoutDashboard className="h-4 w-4" />
              Launch Cockpit
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSignOut}
              className="text-foreground/70 hover:text-foreground"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </nav>
      </header>

      {/* Hero */}
      <main className="relative z-10">
        <section
          id="overview"
          className="mx-auto flex max-w-7xl flex-col items-center gap-12 px-6 pb-16 pt-10 sm:px-8 lg:grid lg:grid-cols-2 lg:items-center lg:gap-16 lg:pb-24 lg:pt-16"
        >
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            className="flex w-full flex-col items-center text-center lg:items-start lg:text-left"
          >
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-xs font-bold uppercase tracking-wide text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              DEPT | Hexaware · GCC Cockpit
            </div>

            <h1 className="mb-5 text-[36px] font-extrabold leading-[1.08] tracking-tight text-foreground sm:text-[52px] lg:text-[60px]">
              Your Workforce,
              <br />
              <span className="text-primary">One GCC Cockpit.</span>
            </h1>

            <p className="mb-9 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
              A unified analytics cockpit for the DEPT | Hexaware GCC — bringing headcount and
              attrition, skills and experience, client-versus-internal utilization, and project
              deployment into one place.
            </p>

            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
              <Button
                size="lg"
                onClick={() => navigate('/')}
                className="h-12 w-full px-8 text-[15px] font-bold shadow-lg shadow-primary/20 transition-transform hover:-translate-y-0.5 sm:w-auto"
              >
                <LayoutDashboard className="h-4 w-4" />
                Launch Cockpit
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="lg"
                onClick={scrollToId('features')}
                className="h-12 w-full bg-card/70 px-8 text-[15px] font-semibold backdrop-blur transition-transform hover:-translate-y-0.5 sm:w-auto"
              >
                Explore Capabilities
              </Button>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.5, ease: 'easeOut', delay: 0.12 }}
            className="w-full max-w-xl lg:max-w-none"
          >
            {/* soft glow behind the floating preview */}
            <div className="relative">
              <div className="pointer-events-none absolute -inset-6 -z-10 rounded-3xl bg-primary/15 blur-2xl" />
              <motion.div animate={floatAnim} transition={floatTransition}>
                <DashboardPreview />
              </motion.div>
            </div>
          </motion.div>
        </section>

        {/* Coverage strip — real dimensions the cockpit spans */}
        <section
          aria-label="What the GCC cockpit covers"
          className="relative z-10 border-y border-border/60 bg-card/30 backdrop-blur-sm"
        >
          <div className="mx-auto grid max-w-7xl grid-cols-2 gap-x-4 gap-y-6 px-6 py-8 sm:px-8 lg:grid-cols-4">
            {DIMENSIONS.map((d) => (
              <div key={d.label} className="flex items-center gap-3.5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <d.icon className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-foreground">{d.label}</p>
                  <p className="truncate text-xs text-muted-foreground">{d.sub}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Capabilities section */}
        <section id="features" className="relative bg-card/40 py-20 backdrop-blur-sm lg:py-24" aria-labelledby="features-heading">
          <div className="mx-auto max-w-7xl px-6 sm:px-8">
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.4 }}
              className="mx-auto mb-14 max-w-2xl text-center"
            >
              <h2
                id="features-heading"
                className="mb-3 text-[28px] font-extrabold tracking-tight text-foreground sm:text-[36px]"
              >
                Everything your GCC needs, in one cockpit
              </h2>
              <p className="text-base leading-relaxed text-muted-foreground sm:text-lg">
                From headcount and attrition to utilization and skills — the same measures your
                Power BI dashboard tracked, rebuilt as a modern, secure portal.
              </p>
            </motion.div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((feature, i) => (
                <motion.div
                  key={feature.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-60px' }}
                  transition={{ duration: 0.35, delay: reduceMotion ? 0 : i * 0.06 }}
                >
                  <FeatureCard
                    icon={feature.icon}
                    title={feature.title}
                    description={feature.description}
                  />
                </motion.div>
              ))}
            </div>

            <motion.div
              id="launch"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.4 }}
              className="mt-14 flex scroll-mt-24 flex-col items-center gap-5 overflow-hidden rounded-2xl border border-primary/20 bg-[linear-gradient(120deg,hsl(215_69%_35%)_0%,hsl(215_75%_42%)_100%)] p-8 text-center shadow-lg sm:flex-row sm:justify-between sm:text-left lg:p-10">
              <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/15 text-white backdrop-blur">
                  <LayoutDashboard className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-xl font-extrabold text-white">Step into the cockpit</p>
                  <p className="text-sm text-white/80">
                    Jump straight into your live GCC workforce dashboard.
                  </p>
                </div>
              </div>
              <Button
                size="lg"
                variant="outline"
                onClick={() => navigate('/')}
                className="h-12 w-full border-white/30 bg-white px-8 text-[15px] font-bold text-primary transition-transform hover:-translate-y-0.5 hover:bg-white sm:w-auto"
              >
                Launch Cockpit
                <ArrowRight className="h-4 w-4" />
              </Button>
            </motion.div>
          </div>
        </section>

        {/* Footer */}
        <footer className="relative border-t border-border/60 py-8">
          <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 sm:flex-row sm:px-8">
            <div className="flex items-center gap-3">
              <img src={deptLogo} alt="DEPT" className="h-5 w-auto object-contain" />
              <span className="h-4 w-px bg-border" />
              <img src={hexawareLogo} alt="Hexaware" className="h-4 w-auto object-contain" />
            </div>
            <p className="text-xs text-muted-foreground">
              DEPT | Hexaware · GCC Cockpit — internal workforce analytics portal.
            </p>
          </div>
        </footer>
      </main>
    </div>
  )
}
