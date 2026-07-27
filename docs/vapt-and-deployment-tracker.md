# VAPT & Deployment Tracker

Development is largely complete (~95%). This tracks what's left: pushing
for VAPT, passing it, and deploying to Azure. See `azure-deployment-plan.md`
for the full Azure architecture/sizing detail — this doc is the short,
checkable step list.

## Step-by-step plan

- [ ] **Get GitHub access** (in progress) — push the `dev` branch to Hexaware GitHub
- [ ] **Submit for VAPT** once pushed — IT runs the security test against the code
- [ ] **Fix any VAPT findings** (if any come back) — expect some, that's normal
- [ ] **VAPT passes** → clear to deploy
- [ ] **Provision Azure resources**: App Service (B1), Static Web Apps, Postgres (B1ms), Key Vault
- [ ] **Add the production redirect URI** to the existing Entra app registration (see IT talking points below)
- [ ] **Set production config** on each resource: `DATABASE_URL`, `CORS_ORIGINS`, `VITE_API_BASE_URL`, Key Vault secrets
- [ ] **Deploy** backend + frontend
- [ ] **Smoke test in production**: SSO login, dashboard data, file upload
- [ ] **DNS/domain cutover**, monitor for the first week or two
- [ ] **(Later, post-launch)** migrate uploaded-file storage to Blob Storage — not blocking go-live

## What to tell the IT person

- **SSO is implemented and working**, currently registered only for local development — the redirect URI on file is `http://localhost:8000/api/auth/saml/acs`. This is expected and normal at this stage; it lets you test locally before the app has a real deployed address.
- **Before/at deployment, a second redirect URI needs to be added to the same Entra app registration** — the real HTTPS URL of the deployed backend (e.g. `https://your-app.azurewebsites.net/api/auth/saml/acs`). Nothing needs to be removed; both URIs can coexist on the same registration.
- **Ask them to confirm**: OIDC is still the confirmed protocol (it was, per the Tenant ID/Client ID/Secret already provided) — just reconfirming before deployment so there's no repeat of the earlier SAML mix-up.
- **Flag that HTTPS is required** for that production redirect URI — Entra won't accept plain `http://` for anything other than `localhost`, so the deployed app must have a working TLS certificate before this step (App Service gives this automatically, so shouldn't be a blocker, just worth saying out loud).
