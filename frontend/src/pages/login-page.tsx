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
  Sparkles,
  ArrowRight,
  BarChart3,
  Clock,
  TrendingUp,
} from 'lucide-react'
import { motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { apiClient, extractErrorMessage } from '@/lib/api-client'
import { useAuth } from '@/lib/auth-context'
import deptLogo from '@/assets/dept-logo-cropped.png'
import hexawareLogo from '@/assets/Blue Logo.png'

// What the user is signing into — grounded in real cockpit modules, no
// numbers (this is a public page). Replaces the dashboard-preview mockup,
// which belongs on the (post-auth) landing page, not here.
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

  const [serverError, setServerError] = React.useState<string | null>(null)

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

  return (
    // Same committed-light background system as the landing page (welcome-page.tsx)
    // — gradient + soft radial glows + dot texture — so login, landing, and the
    // dashboard read as one continuous product. No dark: variants: the app has
    // no dark-mode palette (see welcome-page.tsx note).
    <div className="relative flex min-h-screen w-full items-center justify-center px-4 py-8 sm:px-6 bg-[linear-gradient(160deg,hsl(216,54%,93%)_0%,hsl(215,56%,87%)_55%,hsl(216,52%,91%)_100%)] text-foreground">
      {/* Decorative page background — same blue tone + dot texture + soft wave
          as the card's branding panel, so the whole surface reads as one
          premium system. Clipped by this wrapper's own overflow-hidden. */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div
          className="absolute -left-40 -top-40 h-[560px] w-[560px] rounded-full opacity-70 blur-3xl"
          style={{ background: 'radial-gradient(circle, hsl(215 80% 62% / 0.30), transparent 70%)' }}
        />
        <div
          className="absolute -bottom-40 -right-32 h-[500px] w-[500px] rounded-full opacity-60 blur-3xl"
          style={{ background: 'radial-gradient(circle, hsl(217 90% 66% / 0.24), transparent 70%)' }}
        />
        <div
          className="absolute inset-0 opacity-60"
          style={{
            backgroundImage: 'radial-gradient(circle, hsl(215 42% 52% / 0.2) 1px, transparent 1px)',
            backgroundSize: '24px 24px',
          }}
        />
        <svg
          className="absolute inset-x-0 bottom-0 h-[36vh] w-full"
          viewBox="0 0 1440 400"
          preserveAspectRatio="none"
        >
          <path d="M0,180 C240,280 480,80 720,130 C960,180 1200,320 1440,220 L1440,400 L0,400 Z" fill="hsl(215 65% 55% / 0.10)" />
          <path d="M0,240 C260,320 520,160 760,200 C1000,240 1220,360 1440,280 L1440,400 L0,400 Z" fill="hsl(215 68% 48% / 0.12)" />
        </svg>
      </div>

      {/* Unified card: left branding panel + right form panel. The shake
          animation on auth error is preserved exactly. */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={shake ? { opacity: 1, y: 0, x: [0, -8, 8, -6, 6, -3, 3, 0] } : { opacity: 1, y: 0 }}
        transition={
          shake
            ? { x: { duration: 0.4, ease: 'easeInOut' } }
            : { duration: 0.3, ease: 'easeOut' }
        }
        className="relative z-10 grid w-full max-w-6xl overflow-hidden rounded-3xl border border-border/60 bg-card shadow-[0_40px_90px_-24px_rgba(28,79,151,0.38)] lg:w-[92vw] lg:min-h-[720px] lg:max-w-[1440px] lg:grid-cols-2 xl:min-h-[780px]"
      >
        {/* Left panel — premium branding + value props. Hidden below lg. No
            dashboard mockup here: that peek-at-the-cockpit treatment lives on
            the (post-auth) landing page, not on this public sign-in surface. */}
        <div className="relative hidden flex-col overflow-hidden p-12 lg:flex xl:p-16 bg-[linear-gradient(160deg,hsl(215,44%,96%)_0%,hsl(216,62%,87%)_100%)]">
          {/* layered accent glows for depth */}
          <div
            className="pointer-events-none absolute -right-24 -top-28 h-[360px] w-[360px] rounded-full opacity-70"
            style={{ background: 'radial-gradient(circle at 40% 40%, hsl(215 80% 72% / 0.55), transparent 70%)' }}
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute -bottom-24 -left-20 h-[380px] w-[440px] rounded-full opacity-60"
            style={{ background: 'radial-gradient(circle at 30% 30%, hsl(215 75% 66% / 0.45), transparent 70%)' }}
            aria-hidden="true"
          />
          {/* fine dot texture */}
          <div
            className="pointer-events-none absolute inset-0 opacity-50"
            style={{
              backgroundImage: 'radial-gradient(circle, hsl(215 45% 50% / 0.16) 1px, transparent 1px)',
              backgroundSize: '24px 24px',
            }}
            aria-hidden="true"
          />
          {/* soft brand wave anchoring the bottom edge */}
          <svg
            className="pointer-events-none absolute inset-x-0 bottom-0 h-28 w-full"
            viewBox="0 0 600 120"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path d="M0,58 C150,110 300,18 450,52 C525,68 570,82 600,72 L600,120 L0,120 Z" fill="hsl(215 70% 55% / 0.12)" />
            <path d="M0,82 C160,120 320,50 470,82 C540,96 580,102 600,94 L600,120 L0,120 Z" fill="hsl(215 70% 45% / 0.16)" />
          </svg>

          <div className="relative z-10 flex items-center gap-3.5">
            <img src={deptLogo} alt="DEPT" className="h-7 w-auto object-contain" />
            <span className="h-6 w-px bg-border" />
            <img src={hexawareLogo} alt="Hexaware" className="h-6 w-auto object-contain" />
          </div>

          <div className="relative z-10 mt-10 max-w-md">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wide text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              GCC Cockpit
            </div>
            <h1 className="mb-3 text-[38px] font-extrabold leading-[1.05] tracking-tight text-foreground xl:text-[44px]">
              Welcome back!
            </h1>
            <p className="text-base leading-relaxed text-muted-foreground">
              Sign in to your DEPT | Hexaware GCC workforce cockpit — headcount, utilization, skills,
              and attrition, all in one place.
            </p>
          </div>

          {/* Value-prop highlights — what you're signing into */}
          <ul className="relative z-10 mt-auto space-y-3.5 pt-12">
            {VALUE_PROPS.map((v, i) => (
              <motion.li
                key={v.title}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.35, delay: 0.15 + i * 0.08, ease: 'easeOut' }}
                className="flex items-center gap-3.5"
              >
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-card text-primary shadow-sm ring-1 ring-primary/10">
                  <v.icon className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-bold text-foreground">{v.title}</p>
                  <p className="text-xs text-muted-foreground">{v.sub}</p>
                </div>
              </motion.li>
            ))}
          </ul>
        </div>

        {/* Right panel — the sign-in "login part". On lg it's a floating
            elevated white card on a tinted, dotted surface (matching the
            reference); on mobile it stays flat/clean, where it's the only
            visible panel. */}
        <div className="relative flex items-center justify-center overflow-hidden p-6 sm:p-10 lg:p-12 bg-card lg:bg-[linear-gradient(160deg,hsl(216,44%,95%)_0%,hsl(216,56%,89%)_100%)]">
          <div
            className="pointer-events-none absolute inset-0 hidden opacity-60 lg:block"
            style={{
              backgroundImage: 'radial-gradient(circle, hsl(215 45% 55% / 0.16) 1px, transparent 1px)',
              backgroundSize: '22px 22px',
            }}
            aria-hidden="true"
          />
          <div className="relative z-10 w-full max-w-md lg:rounded-2xl lg:border lg:border-border/60 lg:bg-card lg:px-9 lg:py-12 lg:shadow-[0_28px_56px_-16px_rgba(28,79,151,0.25)]">
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
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
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
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
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
                className="h-12 w-full text-[15px] font-bold shadow-lg shadow-primary/20 transition-transform hover:-translate-y-0.5"
                disabled={loginMutation.isPending}
              >
                {loginMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                {loginMutation.isPending ? 'Signing in…' : 'Sign in'}
                {!loginMutation.isPending && <ArrowRight className="h-4 w-4" />}
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
