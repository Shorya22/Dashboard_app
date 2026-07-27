import * as React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  Loader2,
  Eye,
  EyeOff,
  Mail,
  Lock,
  AlertCircle,
  CheckCircle2,
  Users,
  TrendingUp,
  Sparkles,
  BarChart3,
  Clock,
  ArrowRight,
} from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { apiClient, extractErrorMessage } from '@/lib/api-client'
import { useAuth } from '@/lib/auth-context'
import deptLogo from '@/assets/dept-logo-cropped.png'
import hexawareLogo from '@/assets/Blue Logo.png'

// Grounded in real cockpit modules — no numbers (this is a public page).
const VALUE_PROPS = [
  { icon: BarChart3, title: 'Workforce analytics', sub: 'Headcount, growth & composition' },
  { icon: Clock, title: 'Utilization insights', sub: 'Client vs internal hours' },
  { icon: TrendingUp, title: 'Attrition & retention', sub: 'Joiners, exits & resignation trends' },
]

const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

type LoginFormValues = z.infer<typeof loginSchema>

interface LoginResponse {
  access_token: string
  token_type: string
  expires_in_minutes: number
}

export function LoginPage() {
  const { setAuth } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const reduceMotion = useReducedMotion()
  const locationState = location.state as { registeredEmail?: string } | null
  // One-shot flash message set by RegisterPage after a successful signup.
  // Captured into local state so it survives the history.replaceState
  // below (which clears it from location.state so a refresh doesn't
  // re-show the banner).
  const [registeredEmail] = React.useState<string | null>(
    locationState?.registeredEmail ?? null,
  )
  React.useEffect(() => {
    if (registeredEmail) {
      window.history.replaceState({}, '')
    }
  }, [registeredEmail])

  // Set by the backend's /api/auth/saml/acs redirect on a failed SSO
  // attempt (expired/invalid state, or Microsoft rejecting the code
  // exchange) — surfaced the same way a password-login error is.
  const ssoFailed = new URLSearchParams(location.search).get('sso_error') === '1'
  React.useEffect(() => {
    if (ssoFailed) {
      window.history.replaceState({}, '', location.pathname)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const [showPassword, setShowPassword] = React.useState(false)
  const [shake, setShake] = React.useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  const [serverError, setServerError] = React.useState<string | null>(
    ssoFailed ? 'Sign-in with Microsoft failed. Please try again.' : null,
  )

  const loginMutation = useMutation({
    mutationFn: async (values: LoginFormValues) => {
      const res = await apiClient.post<LoginResponse>('/auth/login', values)
      return res.data
    },
    onSuccess: (data) => {
      setServerError(null)
      setAuth(data.access_token)
      // Always land on the welcome page after login, regardless of what
      // page (if any) the user was redirected here from.
      navigate('/welcome', { replace: true })
    },
    onError: (error) => {
      setServerError(extractErrorMessage(error, 'Unable to sign in. Please try again.'))
      setShake(true)
      window.setTimeout(() => setShake(false), 400)
    },
  })

  const onSubmit = (values: LoginFormValues) => {
    setServerError(null)
    loginMutation.mutate(values)
  }

  const floatAnim = reduceMotion ? undefined : { y: [0, -9, 0] }
  const floatTransition = reduceMotion
    ? undefined
    : { duration: 5.5, repeat: Infinity, ease: 'easeInOut' as const }

  return (
    // Committed-light background system shared with the landing page. No dark:
    // variants (the app has no dark palette).
    <div className="relative flex min-h-screen w-full items-center justify-center overflow-hidden px-4 py-8 sm:px-6 bg-[linear-gradient(155deg,hsl(216,56%,94%)_0%,hsl(215,58%,86%)_55%,hsl(216,54%,90%)_100%)] text-foreground">
      {/* Premium background: layered radial glows, a large elegant dot grid,
          and a soft brand wave. Clipped by this wrapper. */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div
          className="absolute -left-40 -top-40 h-[620px] w-[620px] rounded-full opacity-70 blur-[100px]"
          style={{ background: 'radial-gradient(circle, hsl(215 85% 62% / 0.32), transparent 70%)' }}
        />
        <div
          className="absolute -bottom-48 -right-40 h-[560px] w-[560px] rounded-full opacity-60 blur-[100px]"
          style={{ background: 'radial-gradient(circle, hsl(220 90% 66% / 0.26), transparent 70%)' }}
        />
        <div
          className="absolute left-1/2 top-1/3 h-[420px] w-[720px] -translate-x-1/2 rounded-full opacity-40 blur-[120px]"
          style={{ background: 'radial-gradient(ellipse, hsl(210 90% 72% / 0.20), transparent 70%)' }}
        />
        {/* Large, elegant dot grid — bigger dots, roomier spacing */}
        <div
          className="absolute inset-0 opacity-70"
          style={{
            backgroundImage: 'radial-gradient(circle, hsl(215 42% 50% / 0.18) 2px, transparent 2px)',
            backgroundSize: '34px 34px',
          }}
        />
        <svg className="absolute inset-x-0 bottom-0 h-[34vh] w-full" viewBox="0 0 1440 400" preserveAspectRatio="none">
          <path d="M0,180 C240,280 480,80 720,130 C960,180 1200,320 1440,220 L1440,400 L0,400 Z" fill="hsl(215 65% 55% / 0.10)" />
          <path d="M0,240 C260,320 520,160 760,200 C1000,240 1220,360 1440,280 L1440,400 L0,400 Z" fill="hsl(215 68% 48% / 0.12)" />
        </svg>
      </div>

      {/* Unified card. Interior is a dotted light-lavender surface on lg (both
          panels), white on mobile. Shake on auth error is preserved. */}
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={shake ? { opacity: 1, y: 0, x: [0, -8, 8, -6, 6, -3, 3, 0] } : { opacity: 1, y: 0 }}
        transition={shake ? { x: { duration: 0.4, ease: 'easeInOut' } } : { duration: 0.35, ease: 'easeOut' }}
        className="relative z-10 grid w-full max-w-md overflow-hidden rounded-[28px] border border-white/70 bg-card shadow-[0_50px_100px_-30px_rgba(28,79,151,0.42)] ring-1 ring-black/[0.03] lg:max-w-[1120px] lg:grid-cols-[0.9fr_1fr] lg:bg-[linear-gradient(150deg,hsl(216,46%,95%)_0%,hsl(216,52%,90%)_100%)]"
      >
        {/* dotted texture across the card interior — lg only, larger grid */}
        <div
          className="pointer-events-none absolute inset-0 hidden opacity-60 lg:block"
          style={{
            backgroundImage: 'radial-gradient(circle, hsl(215 45% 52% / 0.16) 2px, transparent 2px)',
            backgroundSize: '30px 30px',
          }}
          aria-hidden="true"
        />
        {/* Central bridge glow — a soft spotlight between the two panels that
            unifies them (Azure-Portal-style lighting). Very subtle. */}
        <div
          className="pointer-events-none absolute left-1/2 top-1/2 hidden h-[560px] w-[620px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-70 blur-[120px] lg:block"
          style={{ background: 'radial-gradient(circle, hsl(214 84% 70% / 0.18), transparent 70%)' }}
          aria-hidden="true"
        />
        {/* Card-spanning wave — flows continuously beneath both panels so the
            surface reads as one, not two isolated columns. */}
        <svg
          className="pointer-events-none absolute inset-x-0 bottom-0 hidden h-44 w-full lg:block"
          viewBox="0 0 1440 220"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d="M0,90 C240,150 480,40 720,74 C960,108 1200,170 1440,120 L1440,220 L0,220 Z" fill="hsl(215 60% 58% / 0.06)" />
          <path d="M0,132 C260,182 520,86 760,118 C1000,150 1220,190 1440,150 L1440,220 L0,220 Z" fill="hsl(215 62% 50% / 0.08)" />
        </svg>

        {/* ── Left / brand panel (lg+) ────────────────────────────────── */}
        <div className="relative z-10 hidden flex-col overflow-hidden p-12 lg:flex">
          {/* soft brand blob behind the mini dashboard */}
          <div
            className="pointer-events-none absolute -bottom-28 -left-28 h-[380px] w-[380px] rounded-full opacity-80"
            style={{ background: 'radial-gradient(circle at 45% 40%, hsl(216 62% 82%), hsl(216 52% 70%))' }}
            aria-hidden="true"
          />

          <div className="relative z-10 flex items-center gap-4">
            <img src={deptLogo} alt="DEPT" className="h-8 w-auto object-contain xl:h-9" />
            <span className="h-6 w-px bg-border xl:h-7" />
            <img src={hexawareLogo} alt="Hexaware" className="h-7 w-auto object-contain xl:h-8" />
          </div>

          <div className="relative z-10 mt-8 max-w-lg">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-white/70 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wide text-primary shadow-sm backdrop-blur">
              <Sparkles className="h-3.5 w-3.5" />
              GCC Cockpit
            </div>
            <h1 className="mb-3 text-[40px] font-extrabold leading-[1.02] tracking-tight text-foreground xl:text-[46px]">
              Welcome back!
            </h1>
            <p className="max-w-md text-[15px] leading-relaxed text-muted-foreground">
              Sign in to your DEPT | Hexaware GCC workforce cockpit — headcount, utilization, skills,
              and attrition, all in one place.
            </p>
          </div>

          {/* Feature cards — hover-lift containers with circular icons */}
          <ul className="relative z-10 mt-7 space-y-1.5">
            {VALUE_PROPS.map((v) => (
              <li
                key={v.title}
                className="group flex items-center gap-3.5 rounded-xl border border-transparent px-2.5 py-2 transition-all duration-200 hover:border-white/70 hover:bg-white/60 hover:shadow-sm"
              >
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-card text-primary shadow-[0_4px_12px_-2px_rgba(28,79,151,0.2)] ring-1 ring-black/[0.03] transition-transform duration-200 group-hover:scale-105 group-hover:text-primary">
                  <v.icon className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-[15px] font-bold leading-tight text-foreground">{v.title}</p>
                  <p className="text-xs text-muted-foreground">{v.sub}</p>
                </div>
              </li>
            ))}
          </ul>

          {/* Mini dashboard — the visual highlight, gently floating */}
          <motion.div
            animate={floatAnim}
            transition={floatTransition}
            className="relative z-10 mt-8 w-[400px] max-w-full rounded-2xl border border-white/70 bg-card/95 p-5 shadow-[0_2px_4px_rgba(28,79,151,0.05),0_12px_24px_-8px_rgba(28,79,151,0.16),0_30px_56px_-18px_rgba(28,79,151,0.32)] backdrop-blur"
          >
            <div className="mb-3.5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10">
                  <Users className="h-4 w-4 text-primary" />
                </div>
                <span className="text-sm font-bold text-foreground">Workforce at a glance</span>
              </div>
              <div className="flex items-center gap-1 rounded-full bg-primary/10 px-2 py-1 text-[10px] font-bold text-primary">
                <TrendingUp className="h-3 w-3" />
              </div>
            </div>

            {/* abstract KPI chips — labels only, no invented figures */}
            <div className="mb-3.5 grid grid-cols-2 gap-2.5">
              {['Utilization', 'Headcount'].map((label, i) => (
                <div key={label} className="rounded-lg border border-border/70 bg-background/70 p-2.5">
                  <p className="mb-1.5 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {label}
                  </p>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary/70"
                      style={{ width: i === 0 ? '72%' : '58%' }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
              <svg width="52" height="52" viewBox="0 0 64 64" aria-hidden="true">
                <circle cx="32" cy="32" r="30" fill="hsl(215 25% 88%)" />
                <path d="M32 32 L32 2 A30 30 0 0 1 60 42 Z" fill="hsl(215 70% 40%)" />
                <path d="M32 32 L60 42 A30 30 0 0 1 20 60 Z" fill="hsl(215 78% 62%)" />
              </svg>
              <div className="flex h-12 items-end gap-2">
                <div className="h-5 w-3 rounded-sm" style={{ background: 'hsl(215 60% 80%)' }} />
                <div className="h-8 w-3 rounded-sm" style={{ background: 'hsl(215 70% 62%)' }} />
                <div className="h-11 w-3 rounded-sm bg-primary" />
              </div>
              <svg width="80" height="42" viewBox="0 0 84 44" className="shrink-0" aria-hidden="true">
                <polyline
                  points="2,34 18,26 34,30 50,14 66,20 82,6"
                  fill="none"
                  stroke="hsl(215 70% 38%)"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
          </motion.div>
        </div>

        {/* ── Right / form panel ──────────────────────────────────────── */}
        {/* On lg the card is left-aligned (justify-start) so it sits closer to
            the left content — removing the central void — rather than floating
            far right. */}
        <div className="relative z-10 flex items-center justify-center p-6 sm:p-10 lg:justify-start lg:py-12 lg:pl-0 lg:pr-6">
          {/* glow behind the sign-in card */}
          <div className="pointer-events-none absolute inset-8 hidden rounded-3xl bg-primary/10 blur-2xl lg:block" aria-hidden="true" />

          <div className="relative w-full max-w-md lg:max-w-[510px] lg:rounded-[22px] lg:border lg:border-white/70 lg:bg-card/80 lg:px-6 lg:py-11 lg:shadow-[0_2px_4px_rgba(28,79,151,0.05),0_16px_32px_-10px_rgba(28,79,151,0.18),0_40px_72px_-22px_rgba(28,79,151,0.34)] lg:ring-1 lg:ring-black/[0.03] lg:backdrop-blur-xl">
            {/* Logos shown here on small screens where the left panel is hidden */}
            <div className="mb-8 flex items-center gap-3.5 lg:hidden">
              <img src={deptLogo} alt="DEPT" className="h-7 w-auto object-contain" />
              <span className="h-6 w-px bg-border" />
              <img src={hexawareLogo} alt="Hexaware" className="h-6 w-auto object-contain" />
            </div>

            <h2 className="mb-1.5 text-[28px] font-extrabold tracking-tight text-foreground">Sign in</h2>
            <p className="mb-7 text-sm text-muted-foreground">
              Use your DEPT | Hexaware account to continue
            </p>

            {registeredEmail && !serverError && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                role="status"
                className="mb-4 flex items-center gap-2.5 rounded-lg border border-primary/30 bg-primary/10 px-3.5 py-2.5 text-sm text-primary"
              >
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>Account created. Sign in with <strong>{registeredEmail}</strong> to continue.</span>
              </motion.div>
            )}

            {serverError && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                role="alert"
                className="mb-4 flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{serverError}</span>
              </motion.div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-[13px] font-semibold text-foreground">
                  Email
                </Label>
                <div className="group relative">
                  <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@company.com"
                    autoComplete="email"
                    aria-invalid={!!errors.email}
                    className={cn('h-12 pl-10', errors.email && 'border-destructive focus-visible:ring-destructive/40')}
                    {...register('email')}
                  />
                </div>
                {errors.email && (
                  <p className="text-xs font-medium text-destructive" role="alert">
                    {errors.email.message}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-[13px] font-semibold text-foreground">
                  Password
                </Label>
                <div className="group relative">
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    aria-invalid={!!errors.password}
                    className={cn(
                      'h-12 pl-10 pr-11',
                      errors.password && 'border-destructive focus-visible:ring-destructive/40',
                    )}
                    {...register('password')}
                  />
                  <button
                    type="button"
                    tabIndex={0}
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-xs font-medium text-destructive" role="alert">
                    {errors.password.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="group h-12 w-full text-[15px] font-bold shadow-lg shadow-primary/25 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary/30 bg-[linear-gradient(180deg,hsl(215,70%,43%)_0%,hsl(215,72%,34%)_100%)]"
                disabled={loginMutation.isPending}
              >
                {loginMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                {loginMutation.isPending ? 'Signing in…' : 'Sign in'}
                {!loginMutation.isPending && (
                  <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
                )}
              </Button>

              <div className="relative py-1 text-center">
                <span className="relative bg-card px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Or
                </span>
                <span className="absolute inset-x-0 top-1/2 -z-10 h-px bg-border" aria-hidden="true" />
              </div>

              <Button
                type="button"
                variant="outline"
                className="h-12 w-full gap-2.5 text-[15px] font-semibold"
                // Real browser navigation, not an axios call — Microsoft's
                // login page can't be loaded inside an XHR/fetch response.
                onClick={() => {
                  window.location.href = '/api/auth/login/microsoft'
                }}
              >
                <svg width="18" height="18" viewBox="0 0 21 21" aria-hidden="true">
                  <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                  <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                  <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                  <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
                </svg>
                Sign in with Microsoft
              </Button>

              <p className="pt-2 text-center text-sm text-muted-foreground">
                Don&apos;t have an account?{' '}
                <Link
                  to="/register"
                  className="font-semibold text-primary hover:underline focus-visible:outline-none focus-visible:underline"
                >
                  Create one
                </Link>
              </p>
            </form>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
