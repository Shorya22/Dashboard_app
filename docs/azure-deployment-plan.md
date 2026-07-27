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
│ (Linux, Basic B1)       │  - Entra ID OIDC / RS256 JWT validation
│ Always-on, manual scale │  - Managed Identity → Key Vault + Blob
└───────────┬────────────┘
            │
   ┌────────┼─────────────┐
   ▼        ▼              ▼
┌────────┐ ┌────────────┐ ┌──────────────┐
│Postgres │ │Key Vault    │ │Blob Storage   │
│Flexible │ │(JWT keys,   │ │(Excel roster/ │
│B1ms     │ │ DB creds)   │ │ booking files)│
└────────┘ └────────────┘ └──────────────┘
```

**Component decisions:**

| Component | Choice | Why |
|---|---|---|
| Frontend | Azure Static Web Apps | Purpose-built for React SPAs, global CDN, free tier fits 50 users |
| Backend | Azure App Service (Linux), **Basic B1** | Sized to actual load: small datasets, low concurrency at 50 users. Basic tier supports Always On (no cold start) but not deployment slots or automatic autoscale — both need Standard tier; not needed at this scale, can upgrade later if real telemetry says otherwise |
| Database | Azure Database for PostgreSQL Flexible Server, **Burstable B1ms** | Cheapest real (non-toy) tier — matches your Postgres-ready migration and this app's low query volume |
| File storage | Azure Blob Storage | Target architecture — persistent across scale-out/redeploys, native versioning/soft-delete for the uploaded roster/booking files. **Phased in after initial launch**: App Service's `/home` directory is the interim storage for the first deployment (works today, zero code change); the upload/versioning code gets migrated to Blob Storage in a follow-up phase, not blocking initial go-live |
| Secrets | Azure Key Vault | Central store for JWT signing keys, DB credentials, accessed via Managed Identity (no secrets in config/app settings) — not yet implemented, planned |
| Identity | Managed Identity (App Service → Key Vault, Blob) | Removes connection strings/keys from app config entirely |

**Rejected/deferred options and why:**
- **Azure VM**: unnecessary ops burden (patching, TLS, reverse proxy) with no benefit over PaaS for this workload.
- **Azure Container Apps**: better fit if/when you split out a background worker (e.g., async Excel processing) or add more services. Not needed for a single FastAPI service today — revisit if the architecture grows multi-service.
- **Combining frontend into the backend App Service** (skip Static Web Apps): considered as a simpler alternative (no CORS/URL config, one resource) but not chosen — staying with the two-resource split since it requires zero code changes (both CORS and the frontend's API base URL are already env-driven).

---

## 3. Sizing Considerations

| Resource | Chosen tier | Why it's enough at ~50 users | Upgrade trigger |
|---|---|---|---|
| App Service | **Basic B1** (1 vCPU, 1.75 GB RAM) | Small datasets (roster/booking/utilization are all a few hundred rows or fewer), low concurrency, no CPU-heavy computation | Sustained high CPU, or memory pressure during Excel upload spikes |
| Postgres | **Burstable B1ms** | Simple queries, small `users` table, low write volume | CPU credit throttling, or sustained (non-bursty) load |
| Blob Storage | Pay-per-GB regardless of tier | Uploaded files are small; cost is negligible either way | N/A — scales automatically |
| Static Web App | Free tier | 100 GB bandwidth included, well above 50-user usage | If bandwidth exceeds included allowance or an SLA is required |

Notes:
- Size App Service RAM for the **Excel upload spike** (pandas/openpyxl loading a workbook into memory), not just steady-state query serving — B1's 1.75 GB has headroom for this given the small file sizes involved.
- Enable **connection pooling** (SQLAlchemy pool, or PgBouncer if concurrency grows) so DB connections aren't reopened per request.
- Consider a **cache layer** (Redis or in-process TTL cache) for dashboard reads, since underlying data only changes on admin upload events — not needed at launch, a later optimization.
- Both App Service and Postgres tiers can be resized after the fact with no downtime and no code change — start small, upgrade based on real telemetry rather than guessing upfront.

---

## 4. Security & Networking Checklist

- [ ] App Service and Postgres in the **same Azure region** (minimize cross-region latency)
- [ ] Postgres Flexible Server on **private access / VNet integration** (no public endpoint) — **verify Basic B1 App Service supports VNet Integration before committing**; this has changed across App Service generations and wasn't confirmed live for this plan. If B1 doesn't support it, either accept a public (firewall-restricted) Postgres endpoint at launch or upgrade this one resource to Standard.
- [ ] App Service **VNet integration** enabled to reach Postgres privately (same caveat as above)
- [ ] **Managed Identity** assigned to App Service; granted access to Key Vault (secrets) and Blob Storage (`Storage Blob Data Contributor`)
- [ ] JWT signing keys and DB credentials stored in **Key Vault**, not app settings
- [ ] CORS restricted to known frontend origin(s) — already done, verify in prod config
- [ ] Blob container for uploads: enable **soft-delete** and **versioning** (part of the Blob Storage migration phase, not initial launch)
- [ ] Confirm PII scrubbing from logs applies to production logging sinks (Application Insights, etc.)

---

## 5. Rollout Plan

**Phase 1 — Infrastructure provisioning**
1. Create resource group (dedicated to this app, separate from unrelated workloads)
2. Provision Postgres Flexible Server (**Burstable B1ms**), in target region
3. Provision Key Vault; load JWT keys and DB connection secrets
4. Provision App Service plan (**Basic B1**) + Web App (Linux, code deploy — no Docker per current org constraints)
5. Provision Static Web App, linked to frontend repo

**Phase 2 — Configuration**
1. Enable Managed Identity on App Service; grant Key Vault access
2. Set environment/config to pull secrets from Key Vault at startup
3. Configure CORS on App Service to allow only the Static Web App origin
4. Set `UPLOAD_STORAGE_DIR` to a path under App Service's persistent `/home` directory (interim storage — see Phase 6)

**Phase 3 — Deployment pipeline**
1. Set up GitHub Actions for App Service deploy (code deploy, once GitHub access lands)
2. Static Web Apps: auto-generated GitHub Actions workflow on resource creation
3. Deployment slots not available on Basic B1 — pre-prod validation happens via a separate low-cost App Service instance if needed, not a same-resource slot swap; revisit if upgrading to Standard later

**Phase 4 — Validation**
1. Smoke test SSO/OIDC flow end-to-end in the deployed environment
2. Load-test with expected concurrent user count; confirm no CPU throttling on Postgres Burstable tier
3. Test Excel upload with a realistic file size; confirm no App Service memory pressure
4. Confirm logs contain no PII in production sink

**Phase 5 — Cutover**
1. DNS cutover from existing Power BI report / staging domain to production Static Web App + App Service custom domains
2. Monitor for 1–2 weeks; revisit tier sizing based on real telemetry (App Service CPU/memory, Postgres CPU credits)

**Phase 6 — Blob Storage migration (post-launch, not blocking go-live)**
1. Provision Blob Storage account + container for uploads; enable soft-delete and versioning
2. Grant App Service's Managed Identity `Storage Blob Data Contributor` on the container
3. Rewrite `backend/app/services/validation/storage.py`'s upload/versioning logic to use the Blob Storage SDK instead of local filesystem calls — a real code change, test thoroughly (locally against Azurite, the Blob Storage emulator, before pointing at the real account)
4. Migrate any files already uploaded to `/home` during initial launch into Blob Storage
5. Switch `UPLOAD_STORAGE_DIR`-equivalent config to the Blob container; remove the `/home` interim path

---

## 6. Open Items to Confirm

- **Confirmed**: expected scale is ~50 users max — drove the B1 / B1ms sizing decisions above
- **Confirmed**: App Service tier = Basic B1, Postgres tier = Burstable B1ms
- **Confirmed**: no Docker (org licensing constraint in progress) — code deploy, not container deploy
- **Confirmed**: Blob Storage is the target file-storage architecture, phased in post-launch (Phase 6), not blocking initial go-live
- Whether Basic B1 App Service actually supports VNet Integration — needs verifying against current Azure docs/portal before the private-Postgres-access checklist items can be executed as written
- Target Azure region (based on user base location)
- Whether high availability (multi-AZ Postgres) is required at launch or can be added later
- Typical Excel upload file size / row count — relevant for the Phase 6 Blob Storage migration sizing, not blocking initial launch
