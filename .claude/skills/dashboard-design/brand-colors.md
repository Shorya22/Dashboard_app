# Confirmed brand colors — DEPT | Hexaware

This is the definitive color source for Dashboard_app. Use ONLY these
colors for brand/UI theming (backgrounds, accents, chart series, header
bar, sidebar). Do not invent additional brand colors or approximate
these visually — use the exact hex values below.

## Hexaware (confirmed official palette, provided directly by the user)

| Name | Hex | RGB | Usage |
|---|---|---|---|
| Hexaware blue | `#3C2CDA` | 60 45 218 | Primary brand blue — logo, key accents |
| Bright blue | `#1D86FF` | 29 134 255 | Secondary/interactive blue — links, active states |
| Electric blue | `#14CBDE` | 20 203 222 | Tertiary accent — sparingly, chart series variety |
| Dark blue | `#07125E` | 7 18 94 | Deep accent, dark-mode surfaces |
| Black | `#040D43` | 4 13 67 | Near-black navy — text on light, header bar base |
| Honey | `#EA9D00` | 235 157 0 | Warm accent — use as DEPT-orange-adjacent secondary warm tone if needed |
| Canary | `#F4CB4E` | 244 203 78 | Warm accent, lighter |
| Error | `#DA2D2C` | 218 45 44 | Negative deltas ONLY (attrition up, exits) — never decorative |
| Light | `#EEEFF2` | 238 239 242 | Light surface / page background |
| White | `#F8F8F9` | 248 248 249 | Card surface |
| Snow | `#FFFFFF` | 255 255 255 | Pure white |
| Border light | `#CBD0E5` | 203 208 229 | Light-mode borders |
| Border dark | `#535983` | 83 89 131 | Dark-mode borders |
| Silver | `#8088A7` | 128 136 167 | Muted/secondary text |

## DEPT (confirmed accent only — full public palette not available)

DEPT's public brand assets (dept.com / deptagency.com) are black/white
only — their logo mark has no embedded color (verified: the SVG in
`frontend/src/assets/logo-dept.svg` uses `fill="black"` exclusively, and
DEPT's official site/brandfetch page could not be scraped for a fuller
palette in this pass). The one DEPT-associated color confirmed directly
by the business owner (matching the Power BI reference PDF's orange
accent bar under the DEPT|HEXAWARE header) is:

| Name | Hex | Usage |
|---|---|---|
| DEPT orange | `#EE6C24` | Primary accent — should be the DOMINANT color across the app (main chart series, primary donut segments, header accent bar, primary CTA buttons) |

**If a fuller official DEPT palette exists (secondary grays, additional
accents), it needs to come from the business owner — do not guess
additional DEPT colors beyond this confirmed orange.**

## How to combine them (confirmed brand rule, per priority instructions)

- **Orange (`#EE6C24`, DEPT) is the DOMINANT/primary color** — main
  chart series, primary donut segments, main trend lines, primary
  buttons/CTAs, header accent bar.
- **Hexaware blue (`#3C2CDA`, or `#1D86FF` for a lighter interactive
  variant) is the SECONDARY/structural color** — comparison series in
  two-series charts, sidebar active-state, links, secondary buttons.
- **Header bar**: navy (`#040D43` or `#07125E`) with the orange
  (`#EE6C24`) accent bar beneath it, matching the reference PDF exactly.
- **Error red (`#DA2D2C`) only for negative deltas** (rising attrition,
  exits) — never decorative, per the dashboard-design skill's existing
  green/red rule (use Hexaware's own red instead of a generic Tailwind
  red).
- **Silver (`#8088A7`) for muted/secondary text and neutral comparison
  series** (the skill's existing "gray for neutral" rule).
- Dark mode: use `#040D43`/`#07125E` as background base, `#535983` for
  borders, keep orange/blue accents at the same hex values (don't shift
  hue for dark mode — only adjust surrounding neutrals).

## Logo assets

- `frontend/src/assets/logo-dept.svg` — DEPT asterisk mark, black fill only (recolor via CSS/currentColor if needed for dark backgrounds)
- `frontend/src/assets/Blue Logo.png` — Hexaware "H" mark, blue/indigo
