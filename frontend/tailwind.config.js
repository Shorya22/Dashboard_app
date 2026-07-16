/** @type {import('tailwindcss').Config} */
const tremorColors = [
  'blue',
  'violet',
  'amber',
  'emerald',
  'cyan',
  'rose',
  'indigo',
  'lime',
  'fuchsia',
  'orange',
  'gray',
  'red',
  // 'sky' and 'slate' are used throughout chart-colors.ts (REGION_COLORS,
  // TYPE_COLORS, CATEGORY_COLORS hash fallback) but were missing here —
  // their utility classes got purged, so any chart/category that resolved
  // to one of these two tokens rendered solid black instead of its color
  // (e.g. Skill Bifurcation by Seniority's "Lead"/"Mid" bars).
  'sky',
  'slate',
]

export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    './node_modules/@tremor/**/*.{js,ts,jsx,tsx}',
  ],
  // Tremor charts pick colors at runtime from the `colors` prop (e.g. `['blue']`),
  // so those utility classes never appear as literal strings in our source and
  // get purged by default. Safelist the full set of brand + category colors
  // used across chart-colors.ts so every chart renders in color, not black.
  safelist: [
    {
      pattern: new RegExp(`^(bg|text|border|ring|fill|stroke)-(${tremorColors.join('|')})-(50|100|200|300|400|500|600|700|800|900|950)$`),
      variants: ['hover', 'ui-selected', 'dark', 'dark:hover'],
    },
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        'accent-orange': {
          DEFAULT: 'hsl(var(--accent-orange))',
          foreground: 'hsl(var(--accent-orange-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 4px)',
        sm: 'calc(var(--radius) - 8px)',
        xl: 'calc(var(--radius) + 4px)',
        '2xl': 'calc(var(--radius) + 8px)',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 2px 6px -1px rgb(15 23 42 / 0.06)',
        'card-hover': '0 12px 24px -6px rgb(15 23 42 / 0.14), 0 4px 8px -2px rgb(15 23 42 / 0.08)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
