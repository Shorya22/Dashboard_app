# Dashboard_app

A workforce/staffing analytics web app replacing a Power BI dashboard —
real authentication, modern professional UI, built from an employee
roster + time-booking export.

Read `PLAN.md` first for the full phased plan.

## Stack (fixed — don't substitute)

- Backend: Python, FastAPI
- Frontend: React + Vite, Tailwind CSS, shadcn/ui, Tremor (charts/KPIs),
  TanStack Table v8, TanStack React Query
- Auth: JWT access token + httpOnly refresh cookie
- Local dev only for now — no Azure/AWS setup yet, Docker Compose comes
  later (see PLAN.md Phase 7)

## Data

Three real source files live in `backend/data/`:
- `DEPT_-_Master_Data_Sheet1_.xlsx` — employee roster (52 rows)
- `UTILIZATION_DATA_SHEET.xlsx` — daily time-booking data (258 rows)
- `PowerBI_Ready_Utilization_May_2026.xlsx` — utilization ground truth (164 rows)

See `.claude/skills/data-model/SKILL.md` for the full schema, known
data-quality issues, and confirmed real Power BI measure names — that
file is the source of truth for anything data-related.

## How to work on this project

- Use the subagents in `.claude/agents/`: `data-agent` for anything
  touching the Excel data, `api-agent` for backend routes/auth,
  `ui-agent` for frontend/charts, `qa-agent` for visual verification
  against the Power BI reference screenshots.
- Ask before touching auth/security code without discussion.
- Don't invent metric names — use the exact measure names confirmed in
  the `data-model` skill (e.g. `Pending Mapping Count`, not "bench count").
