import * as React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Loader2, Eye, EyeOff, Mail, Lock, AlertCircle, CheckCircle2, Users, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { apiClient, extractErrorMessage } from '@/lib/api-client'
import { useAuth } from '@/lib/auth-context'
import deptLogo from '@/assets/dept-logo-cropped.png'
import hexawareLogo from '@/assets/Blue Logo.png'

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
    // Committed-light background system shared with the landing page — blue
    // gradient + dot texture + soft wave — so login, landing, and dashboard
    // read as one system. No dark: variants (the app has no dark palette).
    <div className="relative flex min-h-screen w-full items-center justify-center px-4 py-8 sm:px-6 bg-[linear-gradient(160deg,hsl(216,54%,93%)_0%,hsl(215,56%,87%)_55%,hsl(216,52%,91%)_100%)] text-foreground">
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
        <svg className="absolute inset-x-0 bottom-0 h-[36vh] w-full" viewBox="0 0 1440 400" preserveAspectRatio="none">
          <path d="M0,180 C240,280 480,80 720,130 C960,180 1200,320 1440,220 L1440,400 L0,400 Z" fill="hsl(215 65% 55% / 0.10)" />
          <path d="M0,240 C260,320 520,160 760,200 C1000,240 1220,360 1440,280 L1440,400 L0,400 Z" fill="hsl(215 68% 48% / 0.12)" />
        </svg>
      </div>

      {/* Unified card. Interior is a dotted light-lavender surface on lg (both
          panels), white on mobile. Shake on auth error is preserved. */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={shake ? { opacity: 1, y: 0, x: [0, -8, 8, -6, 6, -3, 3, 0] } : { opacity: 1, y: 0 }}
        transition={shake ? { x: { duration: 0.4, ease: 'easeInOut' } } : { duration: 0.3, ease: 'easeOut' }}
        className="relative z-10 grid w-full max-w-6xl overflow-hidden rounded-3xl border border-border/60 bg-card shadow-[0_40px_90px_-24px_rgba(28,79,151,0.38)] lg:w-[92vw] lg:min-h-[720px] lg:max-w-[1440px] lg:grid-cols-2 lg:bg-[linear-gradient(160deg,hsl(216,43%,95.5%)_0%,hsl(216,50%,91%)_100%)] xl:min-h-[780px]"
      >
        {/* dotted texture across the whole card interior — lg only */}
        <div
          className="pointer-events-none absolute inset-0 hidden opacity-60 lg:block"
          style={{
            backgroundImage: 'radial-gradient(circle, hsl(215 45% 55% / 0.16) 1px, transparent 1px)',
            backgroundSize: '22px 22px',
          }}
          aria-hidden="true"
        />

        {/* Left panel — branding + a peek at the dashboard. Hidden below lg. */}
        <div className="relative z-10 hidden flex-col overflow-hidden p-12 lg:flex xl:p-16">
          {/* large brand blob, anchoring the bottom-left */}
          <div
            className="pointer-events-none absolute -bottom-32 -left-28 h-[500px] w-[500px] rounded-full"
            style={{ background: 'radial-gradient(circle at 42% 38%, hsl(216 64% 73%), hsl(216 56% 61%))' }}
            aria-hidden="true"
          />

          <div className="relative z-10 flex items-center gap-4">
            <img src={deptLogo} alt="DEPT" className="h-8 w-auto object-contain xl:h-9" />
            <span className="h-7 w-px bg-border" />
            <img src={hexawareLogo} alt="Hexaware" className="h-7 w-auto object-contain" />
          </div>

          <div className="relative z-10 mt-10 max-w-md">
            <h1 className="mb-3 text-[40px] font-extrabold leading-[1.05] tracking-tight text-foreground xl:text-[46px]">
              Welcome back!
            </h1>
            <p className="text-base leading-relaxed text-muted-foreground">
              Sign in to access your workforce analytics dashboard.
            </p>
          </div>

          {/* Decorative "at a glance" card — illustrative shapes only, no
              invented figures (this is a public, pre-auth page). */}
          <div className="relative z-10 mt-auto w-[350px] max-w-full rounded-2xl border border-border/60 bg-card p-5 shadow-[0_20px_44px_-14px_rgba(28,79,151,0.28)]">
            <div className="mb-3.5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-muted">
                  <Users className="h-4 w-4 text-primary" />
                </div>
                <span className="text-sm font-bold text-foreground">Workforce at a glance</span>
              </div>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
                <TrendingUp className="h-4 w-4 text-primary" />
              </div>
            </div>

            <div className="flex items-center justify-between gap-3 border-y border-border py-4">
              <svg width="54" height="54" viewBox="0 0 64 64" aria-hidden="true">
                <circle cx="32" cy="32" r="30" fill="hsl(215 25% 88%)" />
                <path d="M32 32 L32 2 A30 30 0 0 1 60 42 Z" fill="hsl(215 70% 40%)" />
                <path d="M32 32 L60 42 A30 30 0 0 1 20 60 Z" fill="hsl(215 78% 62%)" />
              </svg>
              <div className="flex h-12 items-end gap-2">
                <div className="h-5 w-3 rounded-sm" style={{ background: 'hsl(215 60% 80%)' }} />
                <div className="h-8 w-3 rounded-sm" style={{ background: 'hsl(215 70% 62%)' }} />
                <div className="h-11 w-3 rounded-sm bg-primary" />
              </div>
              <svg width="78" height="42" viewBox="0 0 80 44" className="shrink-0" aria-hidden="true">
                <polyline
                  points="2,34 18,26 34,30 50,14 64,20 78,6"
                  fill="none"
                  stroke="hsl(215 70% 38%)"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>

            <p className="mt-3.5 text-center text-xs font-medium text-muted-foreground">
              Headcount, utilization, and attrition — all in one view
            </p>
          </div>
        </div>

        {/* Right panel — the sign-in "login part". On lg it's a floating
            elevated white card on the dotted surface; on mobile it stays
            flat/clean, where it's the only visible panel. */}
        <div className="relative z-10 flex items-center justify-center p-6 sm:p-10 lg:p-12">
          <div className="w-full max-w-md lg:rounded-2xl lg:border lg:border-border/60 lg:bg-card lg:px-9 lg:py-12 lg:shadow-[0_28px_56px_-16px_rgba(28,79,151,0.25)]">
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
