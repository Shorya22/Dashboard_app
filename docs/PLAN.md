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

## Phase 8 — data upload & ingestion validation

Goal: let an admin replace the roster / booking / ground-truth Excel
files from the UI, without a bad upload ever reaching the live cache
`data_loader.py` serves from. One file type uploaded at a time. Any
validation failure — structural or business-rule — rejects the upload
outright; there is no "warn but allow" tier. Every attempt (accepted or
rejected) is kept on disk so an admin can roll back to the previous
active file.

This phase deliberately scopes to what the app's actual current
architecture and scale justify (local dev, Excel + in-memory cache, one
admin, files in the hundreds of rows) — **not** a job-queue /
staging-DB / observability-stack build-out. That heavier tier (async
workers, DB-backed staging tables, OpenTelemetry/Grafana, notifications,
distributed locking) is explicitly deferred until there's a real
database-backed data layer and production deployment to justify it —
see "Deferred to a later phase" at the end of this section.

Owner: **data-agent** first (validation logic + tests), then
**api-agent** (endpoints), then **ui-agent** (upload screen).

### 8a — config-driven validator: generic engine + `pandera`, zero hardcoded values in Python (data-agent, tested against known-good and known-bad fixtures)

**Principle (confirmed 2026-07-21): the validation engine is generic
Python with no dataset-specific knowledge baked in; every closed-set
value, dtype, required/optional flag, and business-rule formula lives
in an editable config file per dataset, not as a Python literal.**
Two different things were previously conflated as "the schema":

- The *structural contract* (a roster file must have a `NEW_EMP_ID`
  column) has to be defined somewhere, always — that's the actual
  point of validation, not hardcoding.
- The *content* of that contract (which GRADE values are valid, the
  experience-sum tolerance) is what must never be a Python literal,
  because it changes over time and shouldn't require a code change +
  redeploy to update.

**New structure:**

- `backend/app/services/validation/schemas/roster.yaml`,
  `booking.yaml`, `ground_truth.yaml` — one declarative config per
  file type. Each defines: `schema_version`, and per column: `dtype`,
  `required` (true/false, derived from actual current usage per the
  2026-07-21 audit), `nullable`, `allowed_values` (for closed-set
  columns), `unique` (for key columns). Also a `business_rules:` list
  of named formula/condition rules (e.g. `total_experience_sum`,
  `lwd_status_pairing`, `date_within_week`), each with its own
  human-readable `reason` string used directly in the validation
  report.
- `backend/app/services/validation/schema_loader.py` — pure, generic:
  reads a YAML config, builds a `pandera.DataFrameSchema` from it
  (dtype/nullable/unique/`Check.isin(allowed_values)`), plus a small
  registry of generic rule *evaluators* (a `sum_equals` evaluator, a
  `conditional_presence` evaluator, a `within_range` evaluator) that
  the config's `business_rules:` entries reference by name and
  parameters — no dataset-specific `if` statement anywhere in this
  file. Adding a new GRADE value, a new required column, or a new rule
  of a kind the evaluator registry already supports is a YAML edit;
  only a genuinely new *kind* of rule (rare) needs a new evaluator.
- `SCHEMA_VERSION` comes from the YAML (`schema_version:` key), bumped
  only when a developer deliberately changes the config (never
  inferred from an upload) — recorded in the validation report and
  upload history so every past upload is auditable against the config
  version it was checked with.
- `GET /api/data/schema/{file_type}` (8b) serializes the YAML config
  directly — the frontend's template/checklist is generated from the
  same file the validator reads, so they can never drift apart.

**Findings from the 2026-07-21 full-file audit that the schemas must
account for** (full detail in `data-model` skill, updated in place):
`Region`/`Working Entity` allowed-value lists include several values
not in the original column dictionary (`APAC`, `Region TBD`, `DTDE`,
`DTUK`, `DTAU`, `Entity TBD`) and no longer include `Hexaware`; roster's
`Declaration Signed` allows `Yes`/`No`/`Pending` (confirmed — unused by
any code today, so this is schema-completeness only); booking's `Month`
column is a real `datetime`, not a display string; ground-truth's
`Weekly Utilization %` is genuinely nullable (5/164 rows) while
`Period Total Utilization %` is not and must additionally be constant
per employee across all its rows; roster's `EMP ID` column must be
explicitly coerced to `str` on read (pandas infers a mixed int/str
object column); booking has no natural single-row primary key — don't
invent a uniqueness `Check` that doesn't hold in the real data; add an
explicit `Check` that `Date` falls within `[Monday of Week, Monday of
Week + 6 days]` (implicit in every existing aggregation, never
enforced).

A thin `validate(df, file_type) -> ValidationReport` wrapper runs
`schema.validate(df, lazy=True)` (pandera's collect-all-errors mode,
not fail-on-first) and converts `SchemaErrors` into the
`{scope, row, column, reason}` report shape the API returns — never a
raw exception.

**Validation pipeline stages, run in order, each stage's failures
collected before stopping (not one giant validator function):**

1. **Security / file-integrity** — before pandas even opens the
   workbook: extension is `.xlsx` (reject `.xlsm`/macros outright),
   under the configured size cap, not password-protected/encrypted, not
   corrupt, no hidden sheets beyond the expected one. Reject
   immediately on failure — never hand a suspicious file to a parser.
2. **Schema validation** — the `pandera` schema above (columns, types,
   allowed values, nullability, uniqueness).
3. **Business-rule validation** — the cross-field `Check`s already
   described (Total Experience sum, LWD/Reason-for-Leaving pairing,
   non-negative experience values, etc.).
4. **Cross-dataset validation — warnings only, never blocks promotion.**
   Roster, booking, and ground-truth are three views of one reality
   (who / activity / computed result), so all three joins matter, but
   they compare two *independently uploaded* files — a temporary
   mismatch (e.g. roster updated a week before booking) is expected,
   not necessarily a bad upload. Confirmed current match rates (as of
   2026-07-21, verified against the real files): booking→roster name
   match 46/46 (100%), ground-truth→roster 40/41 (97.6%, one
   unresolved: `Pramod Kabugande`), booking↔ground-truth reconciliation
   (`reconcile_weekly_utilization`, the one join with live production
   code today) 156/164 employee-weeks (94.2%). None of these are 100%
   even in the current known-good data, so a hard block would be
   unworkable — instead every relevant upload re-runs the applicable
   join(s) against whatever other datasets are currently active and
   surfaces the result (rate + specific unmatched names) in the
   validation report for the admin to judge. Skipped entirely (with a
   note in the report) if the referenced dataset isn't loaded yet.
   The roster↔booking and roster↔ground-truth joins are currently only
   documentation/ad-hoc verification, not real code — this phase
   promotes them into tested validator functions alongside the
   already-live `reconcile_weekly_utilization`.

**File fingerprinting**: compute a SHA-256 hash of the uploaded file on
arrival. If it matches the hash of the currently-active version for
that file type, short-circuit as a no-op ("already uploaded, no
changes") instead of creating a redundant dataset version — this is
also what makes re-submitting the same upload after a network hiccup
safe (idempotent) rather than silently creating a duplicate version.

**Shared dataset-plugin interface** so the three file types don't
duplicate ingestion code and a fourth dataset later is a config
addition, not a new pipeline: `backend/app/services/validation/base.py`
defines a small `DatasetPlugin` protocol (`schema`, `validate_business_rules`,
`validate_cross_dataset`, `file_type_name`); `roster_schema.py` /
`booking_schema.py` / `ground_truth_schema.py` each implement one. The
upload/promotion code in 8b calls through this interface generically
instead of branching on file type.

Also add: `GET /api/data/schema/{file_type}` (api-agent, Step 8b) that
serializes the active schema's column names/types/allowed-values, so
the frontend can show a non-technical admin an upload template/checklist
*before* they upload, not just an error report after.

Fixtures per file type under `backend/tests/fixtures/`: one known-good
file plus one broken file per rule category (wrong columns, bad GRADE
value, Total Experience mismatch, duplicate `NEW_EMP_ID`, a
cross-dataset mismatch, etc.), mirroring the real data-quality issues
the `data-model` skill already documents. One test per rule, asserting
on the specific violation reported.

### 8b — dataset versioning, staged promotion, rollback (api-agent)

- **Dataset versioning, separate from schema versioning**: every
  successful upload for a file type gets the next sequential dataset
  version number (independent of `SCHEMA_VERSION`, which only changes
  on a deliberate code release). Files are **immutable and never
  overwritten** — `backend/data/uploads/<file_type>/v<N>.xlsx` — so
  history is just "which version is active," never a file mutation.
- Upload lands in a quarantine path first and is validated there — the
  active file `data_loader.py` reads is never touched until validation
  passes. On pass, promotion is **atomic**: write the new file fully,
  then update the manifest's active pointer in one step (never leave
  the manifest pointing at a half-written file).
- Per file type, a `manifest.json` tracks: active version number, its
  SHA-256, schema version it validated against, uploaded_by, timestamp,
  and the full history of prior versions with the same fields —
  this is also the audit log (who/when/file/version/outcome).
- On fail: reject with `422` + the structured report; rejected
  attempts are still recorded in history (with `status: rejected`) for
  auditability, but the file itself isn't retained past the request
  (no promotion ever happened, nothing to roll back to).
- `POST /api/data/validate/{file_type}` — **dry-run**: runs the full
  8a pipeline and returns the report (row counts checked / passed /
  failed, full error list) without storing or promoting anything. Lets
  the UI show a preview before the admin commits to uploading.
- `POST /api/data/upload/{file_type}` — admin-only (reuse the
  `admin`/`viewer` role from Phase 3). Runs validation; on the
  fingerprint-duplicate case returns `200` with a "no changes, already
  active as v`N`" result instead of creating a new version. Otherwise
  `200` + report on success (new version promoted) or `422` + report on
  failure.
- `POST /api/data/rollback/{file_type}` — admin-only, restores the
  previous active version from the manifest and reloads the cache.
- `GET /api/data/history/{file_type}` — admin-only, lists past upload
  versions and their outcomes.
- `GET /api/data/report/{file_type}/{version}` — admin-only, downloads
  the stored validation report for a given version as an `.xlsx`
  (row/column/expected/reason/severity) — useful for a non-technical
  admin to hand the report to whoever prepared the source file.
- `GET /api/data/template/{file_type}` — admin-only, returns a blank
  template `.xlsx` with the current schema's expected columns, built
  from the same schema object (never a hand-maintained separate file).
- Max upload size / max rows come from `app/core/config.py`, not a
  hardcoded literal in the upload route.

### 8c — upload UI (ui-agent)

- Admin-only screen, one upload slot per file type (roster / booking /
  ground-truth).
- "Download template" link and current active version shown before
  upload.
- After choosing a file: calls `/validate` first and shows a preview
  (rows checked / passed / errors) before the admin confirms and
  actually calls `/upload`.
- On rejection: render the structured error report row-by-row, with a
  "download report" button, not a generic failure toast.
- On success: confirmation + link to roll back.
- History view backed by `GET /api/data/history/{file_type}`, showing
  version, uploader, timestamp, schema version, status, and a rollback
  button per row.

### Deferred to a later phase (needs infra this app doesn't have yet)

Not part of this phase — revisit once there's a real database-backed
data layer and a production deployment to justify the added complexity:
background job queue / async workers for large-file processing with
progress polling and job IDs, staging database tables (currently there
is no DB for roster/booking/ground-truth data, only for `users`),
distributed/optimistic locking for concurrent admin uploads, a metrics
dashboard and alerting, OpenTelemetry/Grafana/Azure Monitor
instrumentation, Slack/Teams/email notifications, CI-run test
automation (tests exist locally per 8a; running them in CI is blocked
on Phase 7's deployment work), and disaster-recovery/retention policies
(revisit at Phase 7).

## What to explicitly skip until after the deadline

CI/CD pipelines, Sentry/monitoring, automated test suites, caching layer,
multi-environment configs. None of these block a working, secure,
good-looking v1 — add them once the pressure is off.
