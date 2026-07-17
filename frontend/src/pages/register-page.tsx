import * as React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, Eye, EyeOff, Mail, Lock, AlertCircle, Users, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { apiClient, extractErrorMessage } from '@/lib/api-client'
import deptLogo from '@/assets/logo-dept.svg'
import hexawareLogo from '@/assets/Blue Logo.png'

// Mirrors backend `RegisterRequest` (models/auth.py): min 8 chars,
// requires at least one letter and one digit. Keeping the client rule
// aligned with the server rule so users don't get a 422 back for
// something the form could have caught first.
const registerSchema = z
  .object({
    email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .max(128, 'Password is too long')
      .refine((v) => /[a-zA-Z]/.test(v) && /\d/.test(v), {
        message: 'Password must contain at least one letter and one number',
      }),
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    path: ['confirmPassword'],
    message: 'Passwords do not match',
  })

type RegisterFormValues = z.infer<typeof registerSchema>

interface RegisterResponse {
  id: string
  email: string
}

export function RegisterPage() {
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = React.useState(false)
  const [showConfirm, setShowConfirm] = React.useState(false)
  const [shake, setShake] = React.useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: '', password: '', confirmPassword: '' },
  })

  const [serverError, setServerError] = React.useState<string | null>(null)

  const registerMutation = useMutation({
    mutationFn: async (values: RegisterFormValues) => {
      const res = await apiClient.post<RegisterResponse>('/auth/register', {
        email: values.email,
        password: values.password,
      })
      return res.data
    },
    onSuccess: (data) => {
      setServerError(null)
      // Redirect to login with a success banner instead of auto-issuing
      // tokens here — the register endpoint deliberately does not return
      // tokens (see backend/app/api/auth.py) so the user re-enters their
      // credentials once to confirm they can sign in.
      navigate('/login', {
        replace: true,
        state: { registeredEmail: data.email },
      })
    },
    onError: (error) => {
      setServerError(extractErrorMessage(error, 'Unable to create your account. Please try again.'))
      setShake(true)
      window.setTimeout(() => setShake(false), 400)
    },
  })

  const onSubmit = (values: RegisterFormValues) => {
    setServerError(null)
    registerMutation.mutate(values)
  }

  return (
    <div className="relative flex min-h-screen w-full items-center justify-center overflow-hidden px-4 py-6 bg-[linear-gradient(160deg,hsl(215,45%,95%)_0%,hsl(217,60%,82%)_50%,hsl(215,70%,38%)_100%)] dark:bg-[linear-gradient(160deg,#080F38_0%,#0B1866_50%,#1C4F97_100%)]">
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

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={shake ? { opacity: 1, y: 0, x: [0, -8, 8, -6, 6, -3, 3, 0] } : { opacity: 1, y: 0 }}
        transition={
          shake
            ? { x: { duration: 0.4, ease: 'easeInOut' } }
            : { duration: 0.25, ease: 'easeOut' }
        }
        className="relative z-10 flex w-full max-w-[1200px] overflow-hidden rounded-2xl border border-border/60 bg-card shadow-2xl lg:h-[80vh] lg:max-h-[1100px] lg:w-[80vw] lg:max-w-[1800px]"
      >
        <div className="relative hidden flex-1 flex-col overflow-hidden px-12 py-12 lg:flex lg:px-16 bg-[linear-gradient(180deg,hsl(215,30%,97%)_0%,hsl(216,55%,90%)_100%)] dark:bg-[linear-gradient(180deg,#0E1B5E_0%,#081040_100%)]">
          <div
            className="pointer-events-none absolute inset-0 opacity-60 dark:opacity-30"
            style={{
              backgroundImage: 'radial-gradient(circle, hsl(215 65% 45% / 0.35) 1.5px, transparent 1.5px)',
              backgroundSize: '22px 22px',
              backgroundPosition: '20% 75%',
            }}
          />
          <div
            className="pointer-events-none absolute -bottom-36 -left-24 h-[460px] w-[600px] rounded-full opacity-70"
            style={{
              background: 'radial-gradient(circle at 30% 30%, hsl(215 75% 65%), hsl(215 75% 40%))',
            }}
          />

          <div className="relative z-10 flex items-center gap-3.5">
            <img src={deptLogo} alt="DEPT" className="h-14 w-auto dark:invert" />
            <span className="h-5 w-px bg-border" />
            <img src={hexawareLogo} alt="Hexaware" className="h-6 w-auto" />
          </div>

          <div className="relative z-10 mt-10 max-w-md">
            <h1 className="mb-3 text-[36px] font-extrabold leading-tight tracking-tight text-foreground">
              Create your account
            </h1>
            <p className="text-base leading-relaxed text-muted-foreground">
              Join the DEPT | Hexaware workforce analytics workspace.
            </p>
          </div>

          <div className="relative z-10 mt-auto w-[340px] rounded-xl bg-card p-5 shadow-xl">
            <div className="mb-3.5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                  <Users className="h-4 w-4 text-primary" />
                </div>
                <span className="text-[12px] font-semibold text-foreground">Workforce at a glance</span>
              </div>
              <div className="flex items-center gap-1 rounded-full bg-primary/10 px-2 py-1 text-[11px] font-bold text-primary">
                <TrendingUp className="h-3 w-3" />
              </div>
            </div>

            <div className="flex items-center gap-5 border-y border-border py-3.5">
              <svg width="52" height="52" viewBox="0 0 64 64" aria-hidden="true">
                <circle cx="32" cy="32" r="30" fill="hsl(215 20% 90%)" />
                <path d="M32 32 L32 2 A30 30 0 0 1 58 47 Z" fill="hsl(215 70% 38%)" />
                <path d="M32 32 L58 47 A30 30 0 0 1 15 59 Z" fill="hsl(215 75% 65%)" />
              </svg>
              <div className="flex h-11 items-end gap-1.5">
                <div className="h-4 w-2.5 rounded-sm bg-secondary" />
                <div className="h-7 w-2.5 rounded-sm" style={{ background: 'hsl(215 75% 65%)' }} />
                <div className="h-5 w-2.5 rounded-sm bg-muted" />
                <div className="h-10 w-2.5 rounded-sm bg-primary" />
              </div>
              <svg width="60" height="34" viewBox="0 0 70 40" className="shrink-0" aria-hidden="true">
                <polyline
                  points="0,32 14,24 28,28 42,12 56,16 70,4"
                  fill="none"
                  stroke="hsl(215 70% 38%)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>

            <p className="mt-3 text-center text-xs font-medium text-muted-foreground">
              Headcount, utilization, and attrition — all in one view
            </p>
          </div>
        </div>

        <div className="relative flex flex-1 items-center justify-center overflow-hidden px-8 py-10 sm:px-12 bg-[linear-gradient(180deg,hsl(215,30%,97%)_0%,hsl(216,55%,90%)_100%)] dark:bg-[linear-gradient(180deg,#0E1B5E_0%,#081040_100%)]">
          <div
            className="pointer-events-none absolute inset-0 opacity-60 dark:opacity-20"
            style={{
              backgroundImage: 'radial-gradient(circle, hsl(215 65% 45% / 0.35) 1.5px, transparent 1.5px)',
              backgroundSize: '22px 22px',
              backgroundPosition: '20% 75%',
            }}
          />
          <div className="relative w-full max-w-[360px] -translate-y-3 rounded-2xl border border-border/50 bg-card px-7 py-10 shadow-[0_24px_48px_-12px_rgba(28,79,151,0.28)] sm:px-8 sm:py-14">
            <div className="mb-6 flex items-center gap-3.5 lg:hidden">
              <img src={deptLogo} alt="DEPT" className="h-14 w-auto dark:invert" />
              <span className="h-5 w-px bg-border" />
              <img src={hexawareLogo} alt="Hexaware" className="h-6 w-auto" />
            </div>

            <h2 className="mb-1.5 text-[24px] font-extrabold tracking-tight text-foreground">Create account</h2>
            <p className="mb-6 text-sm text-muted-foreground">
              It only takes a minute to get started
            </p>

            {serverError && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                role="alert"
                className="mb-4 flex items-center gap-2.5 rounded-md border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive"
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
                    placeholder="At least 8 characters, with a number"
                    autoComplete="new-password"
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

              <div className="space-y-1.5">
                <Label htmlFor="confirmPassword" className="text-[13px] font-semibold text-foreground">
                  Confirm password
                </Label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="confirmPassword"
                    type={showConfirm ? 'text' : 'password'}
                    placeholder="Re-enter your password"
                    autoComplete="new-password"
                    aria-invalid={!!errors.confirmPassword}
                    className={cn(
                      'h-12 pl-10 pr-11',
                      errors.confirmPassword && 'border-destructive focus-visible:ring-destructive/40',
                    )}
                    {...register('confirmPassword')}
                  />
                  <button
                    type="button"
                    tabIndex={0}
                    onClick={() => setShowConfirm((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                    aria-label={showConfirm ? 'Hide password' : 'Show password'}
                  >
                    {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="text-xs font-medium text-destructive" role="alert">
                    {errors.confirmPassword.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="h-12 w-full text-[15px] font-bold"
                disabled={registerMutation.isPending}
              >
                {registerMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                {registerMutation.isPending ? 'Creating account…' : 'Create account'}
              </Button>

              <p className="pt-2 text-center text-sm text-muted-foreground">
                Already have an account?{' '}
                <Link
                  to="/login"
                  className="font-semibold text-primary hover:underline focus-visible:outline-none focus-visible:underline"
                >
                  Sign in
                </Link>
              </p>
            </form>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
