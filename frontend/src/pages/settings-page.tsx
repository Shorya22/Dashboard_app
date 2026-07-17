import { Check, Palette } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { CATEGORY_COLORS } from '@/lib/chart-colors'
import {
  CHART_THEMES,
  CHART_THEME_ORDER,
  useChartTheme,
  setActiveChartTheme,
  type ChartThemeName,
} from '@/lib/chart-theme-store'

/** Small swatch strip previewing a theme's 8-slot categorical palette in
 * its real fixed order — the same order every chart on the app draws from,
 * so this preview is an honest look at what picking the theme actually
 * changes, not a decorative approximation. */
function ThemeSwatches({ theme }: { theme: ChartThemeName }) {
  const hex = CHART_THEMES[theme].hex
  return (
    <div className="flex gap-1.5">
      {CATEGORY_COLORS.map((token) => (
        <span
          key={token}
          className="h-6 w-6 shrink-0 rounded-full border border-black/5"
          style={{ backgroundColor: hex[token] }}
        />
      ))}
    </div>
  )
}

export function SettingsPage() {
  const activeTheme = useChartTheme()

  return (
    <div className="space-y-5">
      <Card className="rounded-2xl border-border bg-card shadow-card">
        <CardHeader className="flex flex-row items-center gap-3 space-y-0">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Palette className="h-5 w-5" />
          </span>
          <div>
            <CardTitle>Chart Color Theme</CardTitle>
            <CardDescription>
              Changes the color palette used across every chart on every page — bars, lines, and
              donuts. Takes effect immediately and is remembered on this device.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {CHART_THEME_ORDER.map((name) => {
            const theme = CHART_THEMES[name]
            const isActive = name === activeTheme
            return (
              <button
                key={name}
                type="button"
                onClick={() => setActiveChartTheme(name)}
                aria-pressed={isActive}
                className={cn(
                  'flex flex-col items-start gap-3 rounded-xl border p-4 text-left transition-colors',
                  isActive
                    ? 'border-primary bg-primary/5 ring-1 ring-primary'
                    : 'border-border hover:bg-muted/50',
                )}
              >
                <div className="flex w-full items-center justify-between">
                  <span className="font-semibold text-card-foreground">{theme.label}</span>
                  {isActive && (
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <Check className="h-3.5 w-3.5" />
                    </span>
                  )}
                </div>
                <ThemeSwatches theme={name} />
                <p className="text-xs text-muted-foreground">{theme.description}</p>
              </button>
            )
          })}
        </CardContent>
      </Card>
    </div>
  )
}
