# Dashboard web app — end-to-end plan

Goal: replace/extend the current Power BI dashboard with a web app that has
real authentication and a modern, professional analytics UI, backed by a
FastAPI + React stack. Deadline-driven, but built so it can grow into a real
product afterward.

**Domain**: this is a workforce/staffing dashboard — headcount, attrition,
tenure, grade distribution, and client/PM deployment tracking from an
employee roster export. See `.claude/skills/data-model/SKILL.md` for the
exact schema and metric definitions — that file is the source of truth,
not this plan.

## How the pieces work together

- **CLAUDE.md** (create at project root) — always-on context: this file is
  where you'd note "backend is FastAPI, frontend is React+Vite, don't use
  MySQL, auth is JWT." Keep it short; procedures go in skills, not here.
- **Skills** (`.claude/skills/`) — reusable knowledge Claude Code loads
  automatically when relevant. Four included here: `data-model` (exact
  schema, metric definitions, data-quality rules for the workforce Excel —
  read this one first), `dashboard-design` (chart types, colors, layout
  rules, component catalog), and `api-conventions` (endpoint shape, auth,
  error format). Drop your Power BI screenshots into
  `.claude/skills/dashboard-design/reference/` so Claude can match them.
- **Subagents** (`.claude/agents/`) — isolated workers for a specific slice
  of the job, so data correctness, backend work, frontend work, and visual
  QA don't blur together in one long session. Four included: `data-agent`
  (schema, cleaning, tested aggregations — works first), `api-agent`,
  `ui-agent`, `qa-agent`.
- **MCP** — connect GitHub MCP, Context7, and Playwright MCP (the qa-agent
  needs Playwright to actually see the running app).

## Phase 0 — setup (day 1, first hour)

1. `git init`, create the repo, connect GitHub MCP.
2. Create `CLAUDE.md` at the root with: stack choices, folder layout,
   how to run dev servers, and "ask before touching auth/security code."
3. Drop this `PLAN.md`, the `.claude/skills/`, and `.claude/agents/`
   folders into the repo root.
4. Put your Power BI screenshots in
   `.claude/skills/dashboard-design/reference/`.
5. Put a sample (masked) Excel file in `backend/data/sample/` so the
   api-agent can build parsing logic against real columns.

## Phase 1 — data layer

Owner: **data-agent**

- Read the workforce Excel with pandas, following `data-model` exactly
- Run the validation checklist from that skill (Total Experience
  consistency, LWD/Reason for Leaving pairing with Status, etc.) and
  surface any data-quality issues found in the real file
- Build and test aggregation functions: headcount, attrition rate,
  average tenure, GCC ratio, bench count, grade distribution — one
  function per metric, one test per function against known values
- Resolve the multi-value `Client`/`Project Manager` handling question
  with you before building any per-client headcount chart

## Phase 2 — backend foundation

Owner: **api-agent**

- FastAPI project skeleton: `app/main.py`, `app/api/`, `app/core/`,
  `app/models/`, `app/services/`
- Health check endpoint `/health`
- Wire data-agent's tested aggregation functions into REST endpoints —
  routes stay thin, no aggregation logic duplicated here
- Pydantic response models for every endpoint (typed, validated)

## Phase 3 — authentication

Owner: **api-agent**

- User model (email, hashed password, role)
- `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout`
- JWT access token (short-lived) + httpOnly refresh cookie
- Role field from day one (`admin` / `viewer`) even if unused yet
- Rate limiting on the login endpoint

## Phase 4 — frontend shell

Owner: **ui-agent**

- Vite + React + Tailwind + shadcn/ui installed
- Login page wired to `/api/auth/login`
- App shell: sidebar nav, top bar, protected route wrapper that checks
  the access token and redirects to login if missing/expired
- React Query set up for data fetching, with the access token attached
  to every request

## Phase 5 — dashboard, charts, visualizations

Owner: **ui-agent**, following the `dashboard-design` skill strictly

- KPI card row wired to real aggregation endpoints
- Primary trend chart (Tremor/Recharts line or bar, per the skill's rules)
- Secondary breakdown chart
- Filter bar (date range, category dropdowns) that updates all charts
  on the page together — not per-chart
- Data table with sort + pagination
- Export button (CSV at minimum; PDF/Excel export later)

## Phase 6 — visual QA loop

Owner: **qa-agent** (needs Playwright MCP)

Repeat per screen:
1. qa-agent loads the running page in a real browser, screenshots it
2. Compares against the Power BI reference screenshots and the
   `dashboard-design` skill's rules
3. Reports concrete deltas (wrong chart type, spacing, missing filter)
4. ui-agent fixes exactly those deltas
5. Repeat until qa-agent reports no meaningful gaps

## Phase 7 — containerize and deploy

- `Dockerfile` for backend, `Dockerfile` for frontend, one
  `docker-compose.yml` tying them together — run this locally first
- For the near-term deadline: deploy backend to Railway/Render, frontend
  to Vercel — skip Azure/AWS setup until there's time for it
- Later: same Docker images move to Azure Container Apps / AWS ECS
  without a rewrite

## What to explicitly skip until after the deadline

CI/CD pipelines, Sentry/monitoring, automated test suites, caching layer,
multi-environment configs. None of these block a working, secure,
good-looking v1 — add them once the pressure is off.
