# Azure Deployment Plan — Workforce/Staffing Analytics Dashboard

## 1. Overview

**Application**: FastAPI (Python) backend + React frontend, replacing an existing Power BI report. Reads employee roster and time-booking data (Excel-based, with admin upload/refresh), backed by a database for user accounts and sessions.

**Security work already completed**:
- SSO via Microsoft Entra ID (OIDC)
- Authentication enforced on all API endpoints
- JWT signed with RS256 (asymmetric keys)
- Database made Postgres-ready (SQLite for local dev, config-driven switch to Postgres for prod)
- CORS restricted, secure cookie handling, PII removed from logs

**Goal of this plan**: define target Azure architecture, service tiers, cost, and rollout steps for production deployment.

---

## 2. Target Architecture

```
┌───────────────────────┐
│ Azure Static Web App   │  React SPA (CDN-hosted, free SSL, custom domain)
└───────────┬────────────┘
            │ HTTPS
            ▼
┌───────────────────────┐
│ Azure App Service       │  FastAPI backend
│ (Linux, Standard tier)  │  - Entra ID OIDC / RS256 JWT validation
│ Always-on, auto-scale   │  - Managed Identity → Key Vault + Blob
└───────────┬────────────┘
            │
   ┌────────┼─────────────┐
   ▼        ▼              ▼
┌────────┐ ┌────────────┐ ┌──────────────┐
│Postgres │ │Key Vault    │ │Blob Storage   │
│Flexible │ │(JWT keys,   │ │(Excel roster/ │
│Server   │ │ DB creds)   │ │ booking files)│
└────────┘ └────────────┘ └──────────────┘
```

**Component decisions:**

| Component | Choice | Why |
|---|---|---|
| Frontend | Azure Static Web Apps | Purpose-built for React SPAs, global CDN |
| Backend | Azure App Service (Linux) | Single service, no cold start (always-on), auto-scale, simpler ops than Container Apps for one monolithic API |
| Database | Azure Database for PostgreSQL Flexible Server | Matches your Postgres-ready migration; fits bursty business-hours usage |
| File storage | Azure Blob Storage | Persistent across scale-out/redeploys, versioning/soft-delete — do **not** use App Service local disk |
| Secrets | Azure Key Vault | Central store for JWT signing keys, DB credentials, accessed via Managed Identity (no secrets in config/app settings) |
| Identity | Managed Identity (App Service → Key Vault, Blob) | Removes connection strings/keys from app config entirely |

**Rejected/deferred options and why:**
- **Azure VM**: unnecessary ops burden (patching, TLS, reverse proxy) with no benefit over PaaS for this workload.
- **Azure Container Apps**: better fit if/when you split out a background worker (e.g., async Excel processing) or add more services. Not needed for a single FastAPI service today — revisit if the architecture grows multi-service.

---

## 3. Sizing Considerations (tier/plan selection left to you)

| Resource | What drives the sizing decision | Upgrade trigger |
|---|---|---|
| App Service | Concurrent users, RAM needed for Excel upload/parsing spikes | CPU sustained high, or auto-scale hitting max instances regularly |
| Postgres | Query load, concurrency, whether sustained vs. bursty | CPU credit throttling (if using a burstable-style plan), or sustained load |
| Blob Storage | Pay-per-GB regardless of tier | N/A — scales automatically |
| Static Web App | Bandwidth, SLA needs | If bandwidth exceeds included allowance or SLA needed |

Notes:
- Size App Service RAM for the **Excel upload spike** (pandas/openpyxl loading a workbook into memory), not just steady-state query serving.
- Enable **connection pooling** (SQLAlchemy pool, or PgBouncer if concurrency grows) so DB connections aren't reopened per request.
- Consider a **cache layer** (Redis or in-process TTL cache) for dashboard reads, since underlying data only changes on admin upload events.

---

## 4. Security & Networking Checklist

- [ ] App Service and Postgres in the **same Azure region** (minimize cross-region latency)
- [ ] Postgres Flexible Server on **private access / VNet integration** (no public endpoint)
- [ ] App Service **VNet integration** enabled to reach Postgres privately
- [ ] **Managed Identity** assigned to App Service; granted access to Key Vault (secrets) and Blob Storage (`Storage Blob Data Contributor`)
- [ ] JWT signing keys and DB credentials stored in **Key Vault**, not app settings
- [ ] CORS restricted to known frontend origin(s) — already done, verify in prod config
- [ ] Blob container for uploads: enable **soft-delete** and **versioning**
- [ ] Confirm PII scrubbing from logs applies to production logging sinks (Application Insights, etc.)

---

## 5. Rollout Plan

**Phase 1 — Infrastructure provisioning**
1. Create resource group (dedicated to this app, separate from unrelated workloads)
2. Provision Postgres Flexible Server (Burstable B2s), private access, in target region
3. Provision Blob Storage account + container for uploads
4. Provision Key Vault; load JWT keys and DB connection secrets
5. Provision App Service plan (Standard S2) + Web App (Linux, container or code deploy)
6. Provision Static Web App, linked to frontend repo

**Phase 2 — Configuration**
1. Enable Managed Identity on App Service; grant Key Vault + Blob access
2. Configure App Service VNet integration → Postgres private endpoint
3. Set environment/config to pull secrets from Key Vault at startup
4. Configure CORS on App Service to allow only the Static Web App origin
5. Point FastAPI's Excel upload endpoint at Blob Storage (stream, don't write to local disk)

**Phase 3 — Deployment pipeline**
1. Set up GitHub Actions (or Azure DevOps) for App Service deploy (container build + push, or code deploy)
2. Static Web Apps: auto-generated GitHub Actions workflow on resource creation
3. Add staging slot on App Service for pre-prod validation before swap

**Phase 4 — Validation**
1. Smoke test SSO/OIDC flow end-to-end in the deployed environment
2. Load-test with expected concurrent user count; confirm no CPU throttling on Postgres Burstable tier
3. Test Excel upload with a realistic file size; confirm no App Service memory pressure
4. Confirm logs contain no PII in production sink

**Phase 5 — Cutover**
1. DNS cutover from existing Power BI report / staging domain to production Static Web App + App Service custom domains
2. Monitor for 1–2 weeks; revisit tier sizing based on real telemetry (App Service CPU/memory, Postgres CPU credits, Blob usage)

---

## 6. Open Items to Confirm

- Expected concurrent user count and usage pattern (steady vs. bursty at specific times)
- Typical Excel upload file size / row count (affects App Service RAM sizing)
- Whether private VNet access to Postgres is a hard security requirement or a nice-to-have (affects App Service tier choice)
- Target Azure region (based on user base location)
- Whether high availability (multi-AZ Postgres) is required at launch or can be added later
- Specific service tiers/plans for App Service and Postgres (your choice, based on budget and expected load)
