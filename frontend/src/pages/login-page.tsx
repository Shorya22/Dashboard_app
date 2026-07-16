import * as React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { Loader2, Eye, EyeOff } from 'lucide-react'
import { motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'
import { apiClient, extractErrorMessage } from '@/lib/api-client'
import { useAuth } from '@/lib/auth-context'
import deptLogo from '@/assets/logo-dept.svg'
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

/**
 * Floating-label text field. Keeps a real <label htmlFor> associated with the
 * input for accessibility; the "floating" effect is purely a transform driven
 * by focus/filled state, so screen readers and keyboard nav are unaffected.
 */
interface FloatingInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  endAdornment?: React.ReactNode
}

const FloatingInput = React.forwardRef<HTMLInputElement, FloatingInputProps>(
  ({ label, error, endAdornment, id, className, onFocus, onBlur, ...props }, ref) => {
    const [focused, setFocused] = React.useState(false)
    const [filled, setFilled] = React.useState(!!props.value || !!props.defaultValue)
    const floated = focused || filled

    return (
      <div className="space-y-1.5">
        <div className="relative">
          <input
            id={id}
            ref={ref}
            className={cn(
              'peer flex h-14 w-full rounded-md border border-input bg-white px-4 pt-4 pb-1.5 text-sm text-foreground',
              'transition-all duration-200 ease-out',
              'placeholder:text-transparent',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-orange/50 focus-visible:border-accent-orange/60',
              error && 'border-destructive focus-visible:border-destructive focus-visible:ring-destructive/40',
              endAdornment && 'pr-11',
              className,
            )}
            onFocus={(e) => {
              setFocused(true)
              onFocus?.(e)
            }}
            onBlur={(e) => {
              setFocused(false)
              setFilled(!!e.target.value)
              onBlur?.(e)
            }}
            onChange={(e) => {
              setFilled(!!e.target.value)
              props.onChange?.(e)
            }}
            aria-invalid={!!error}
            placeholder={label}
            {...props}
          />
          <Label
            htmlFor={id}
            className={cn(
              'pointer-events-none absolute left-4 origin-left text-muted-foreground transition-all duration-200 ease-out',
              floated ? 'top-2 -translate-y-0 scale-75 text-accent-orange' : 'top-1/2 -translate-y-1/2 scale-100',
              error && floated && 'text-destructive',
            )}
          >
            {label}
          </Label>
          {endAdornment && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">{endAdornment}</div>
          )}
        </div>
        {error && (
          <p className="text-xs font-medium text-destructive" role="alert">
            {error}
          </p>
        )}
      </div>
    )
  },
)
FloatingInput.displayName = 'FloatingInput'

export function LoginPage() {
  const { setAuth } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: Location })?.from?.pathname ?? '/'

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
      navigate(from, { replace: true })
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
    <div className="flex min-h-screen w-full items-center justify-center bg-background px-4 py-10">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={shake ? { opacity: 1, y: 0, x: [0, -8, 8, -6, 6, -3, 3, 0] } : { opacity: 1, y: 0 }}
        transition={
          shake
            ? { x: { duration: 0.4, ease: 'easeInOut' } }
            : { duration: 0.25, ease: 'easeOut' }
        }
        className="w-full max-w-md"
      >
        <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
          <div className="h-1.5 w-full bg-accent-orange" />

          <div className="space-y-6 px-8 pt-8 sm:px-10">
            <div className="flex items-center gap-3">
              <img src={deptLogo} alt="DEPT" className="h-8 w-auto shrink-0" />
              <span className="h-6 w-px bg-border" />
              <img src={hexawareLogo} alt="Hexaware" className="h-7 w-auto shrink-0" />
            </div>

            <div className="space-y-1">
              <h1 className="text-2xl font-bold tracking-tight text-foreground">Sign in</h1>
              <p className="text-sm text-muted-foreground">
                DEPT | Hexaware workforce analytics dashboard
              </p>
            </div>
          </div>

          <form
            className="space-y-5 px-8 pb-6 pt-6 sm:px-10"
            onSubmit={handleSubmit(onSubmit)}
            noValidate
          >
            <FloatingInput
              id="email"
              type="email"
              label="Email"
              autoComplete="email"
              error={errors.email?.message}
              {...register('email')}
            />

            <FloatingInput
              id="password"
              type={showPassword ? 'text' : 'password'}
              label="Password"
              autoComplete="current-password"
              error={errors.password?.message}
              endAdornment={
                <button
                  type="button"
                  tabIndex={0}
                  onClick={() => setShowPassword((v) => !v)}
                  className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-orange/40"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
              {...register('password')}
            />

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <Checkbox id="remember-me" />
                Remember me
              </label>
              <button
                type="button"
                className="text-xs text-muted-foreground underline-offset-2 transition-colors hover:text-accent-orange hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-orange/40"
              >
                Forgot password?
              </button>
            </div>

            {serverError && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                role="alert"
                className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {serverError}
              </motion.div>
            )}

            <Button type="submit" className="w-full" disabled={loginMutation.isPending}>
              {loginMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Sign in
            </Button>
          </form>
          <div className="border-t border-border px-8 py-4 text-center text-xs text-muted-foreground sm:px-10">
            New to the platform? Contact your admin
          </div>
        </div>
      </motion.div>
    </div>
  )
}
