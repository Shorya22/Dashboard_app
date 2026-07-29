# Dashboard_app — SaaS Platform Feature Roadmap

Turning Dashboard_app from a single-purpose utilization dashboard into a
full RBAC-driven, multi-module, production-grade SaaS platform — where
what a user sees is entirely a function of who they are.

---

## 1. Login & Roles

- Real authenticated login (already built) — email/password + Microsoft SSO
- Each user assigned one or more roles (e.g. "HR Ops Viewer", "Fin Ops
  Editor") rather than one flat "admin/viewer" tag
- Roles are reusable templates — define once, assign to many people

**Example:** Sakshi logs in and is assigned the role "HR Ops Editor." Ashish
logs in with "TA Metrics Viewer." Same login page, completely different
experience once inside.

---

## 2. Modules

- App split into distinct sections: TA Metrics, Tech Ops (onboarding), HR
  Ops, Fin Ops, Operations Report, Admin
- A role determines which modules show up at all — others don't appear in
  the menu, and the underlying pages/APIs are blocked even if someone tries
  a direct link
- Modules with no page built yet (TA Metrics, Tech Ops, Fin Ops) can start
  as empty placeholders and get real screens later without redoing the
  access system

**Example:** When Milind logs in, he sees "Operations Report" in the menu.
He does not see "Fin Ops" at all — it's not just locked, it's invisible to
him, like it doesn't exist.

---

## 3. View vs Edit

- Two permission levels within a module: View-only, or View+Edit/Upload
- Named module owners (Sakshi–HR Ops, Ashish–TA Metrics, Abhishek/Anuj–Fin
  Ops, Milind–Operations Report) would typically get Edit; their teams get
  View
- Same rule applies everywhere in that module — no separate per-screen
  exceptions to track

**Example:** Sakshi (HR Ops owner) can upload new HR data and edit records.
Someone else on her team with "HR Ops Viewer" can open the same dashboard,
see the same charts, but there's no upload button and no edit option —
read-only.

---

## 4. Flexible Data-Level Filtering

- Beyond "which module," restrict which rows a user sees inside a module
- Not locked to one attribute — could be region, client, department, or
  anything else the data has
- Composes with modules: e.g. an HR Ops user scoped to one region only sees
  HR data for that region, nothing else
- Designed so a new filtering attribute can be added later as
  configuration, not a rebuild

**Example:** Two people both have "HR Ops Viewer." One is scoped to EMEA,
the other to APAC. They see the exact same HR Ops screen, but the charts
and tables show completely different numbers — each only sees their own
slice. Another example: could just as easily be scoped by client instead of
region — e.g. a client-facing manager only sees data for their one client,
not the whole roster.

---

## 5. Admin Panel

- One dedicated screen (module) for managing the whole system
- Create/manage users, assign roles, assign module access, assign
  data-scope — all without a developer touching code
- This is the "control room" — the thing that makes points 1-4
  configurable day-to-day

**Example:** A new employee joins as the Fin Ops analyst for AMER. Instead
of asking a developer to change code, an admin goes to the Admin Panel,
creates the user, assigns "Fin Ops Viewer" + "AMER" scope, and they're
ready to log in — takes two minutes.

---

## 6. Excel-Upload-Only, Database as Source of Truth

- Excel is only how raw data enters the system — never read live by the
  dashboard again
- Upload → validate → clean/standardize → save as a new snapshot → import
  into the database as one all-or-nothing action
- Every dashboard screen, chart, and export always reads from the
  database's current approved snapshot, never the uploaded file directly

**Example:** HR uploads June's roster Excel file. The app validates it,
cleans it, and loads it into the database. From that point on, every chart
on every dashboard reads from the database — even if someone opens that
original Excel file and edits a cell, nothing on the dashboard changes,
because the app never looks at that file again.

---

## 7. Snapshot Approval Workflow

- New uploads don't go live instantly — they move through stages: Draft →
  Validated → Pending Approval → Approved → Active → Archived
- Someone has to approve a new version before it becomes what everyone sees
- Any earlier approved version can be restored instantly (rollback) if a
  bad upload slips through

**Example:** Someone uploads July data with a mistake (wrong hours format).
It sits as "Pending Approval." An admin reviews it, notices the issue, and
doesn't approve it — June's data (still "Active") keeps showing on the
dashboard until a corrected July file is approved. If a bad file did get
approved, rollback restores June instantly.

---

## 8. Full Validation Report

- When a file is uploaded, every problem is checked and reported together
  in one pass — not one error at a time, requiring re-upload after each fix
- Covers: file safety (corrupt/password-protected/macro-laced files),
  correct columns/data types, business rules (valid market, hours ≤ 24,
  unique employee IDs), and cross-checks against other datasets (e.g. does
  this employee actually exist in the roster)

**Example:** Someone uploads a file missing a column and with 3 rows that
have invalid hours (e.g. 30 hours in a day). Instead of the system
rejecting it after the first problem and making them re-upload three
separate times, it comes back with one report: "Missing column:
Department; Row 12: hours exceed 24; Row 45: hours exceed 24; Row 88: hours
exceed 24." Fix everything at once, re-upload once.

---

## 9. Full Audit Trail

- Every meaningful action is logged: who uploaded what, who validated it,
  who approved it, who activated or rolled back a version, and when
- Separate from, but similar in spirit to, the access log in point 11 —
  this one is about data changes, not who accessed what

**Example:** Six months later, someone asks "why did July's utilization
numbers change?" The audit trail shows: "Milind uploaded July v2 on July
15, admin approved it on July 16, replacing v1 which had a data entry
error." Full story, no guessing.

---

## 10. Deactivate Users

- Removing someone's access doesn't mean deleting their account
- Mark them Inactive instead — their access is cut off immediately, but
  their history (what they uploaded, approved, viewed) stays intact for the
  audit trail
- Keeps historical reports accurate even after someone leaves

**Example:** An employee managing Fin Ops leaves the company. Their account
is marked Inactive — they can no longer log in starting immediately — but
the audit trail still shows every file they uploaded and approved while
they worked there, so historical reports don't break.

---

## 11. Activity Log

- Tracks who accessed what, and importantly, any access attempts that were
  denied
- Useful for answering "did anyone outside EMEA ever see EMEA HR data" if
  that's ever questioned
- Different from point 9 — this is about access/security events, not data
  changes

**Example:** If there's ever a concern that someone saw data they
shouldn't have, the activity log can answer: "Did this AMER-scoped user
ever attempt to view EMEA data?" — showing the attempt and that it was
blocked, or confirming it never happened.

---

## 12. Export Protection

- If a user downloads a table or chart as CSV/Excel, the export only
  contains what they're allowed to see on-screen
- Prevents someone with restricted view access from getting the full
  unrestricted dataset just by clicking "Export"

**Example:** An APAC-scoped user clicks "Export to Excel" on the
Utilization table. The downloaded file only contains APAC rows — they can't
get the full company dataset just by exporting instead of viewing
on-screen.

---

## 13. AI Chatbot (Future)

- Not building this now — explicitly flagged as backlog
- Architecture is being kept open so it can be added later (e.g. a chatbot
  that answers questions using the same database and same access rules as
  everything else) without redesigning the system

**Example (future capability):** eventually, Sakshi could
type "how many people in EMEA are on the bench right now" into a chatbot,
and it would answer using the same live database and same access rules —
she still couldn't ask about Fin Ops data she has no access to.
