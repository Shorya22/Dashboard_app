# Running Dashboard_app with Docker Compose

This containerizes the backend (FastAPI), frontend (React/Vite built
static bundle, served by nginx), and a Cloudflare tunnel for a public URL.

## Quick start

```bash
docker compose build
docker compose up -d
docker compose ps
```

- Backend: http://localhost:8000 (also reachable inside the compose
  network as `http://backend:8000`)
- Frontend: http://localhost:8080 (nginx proxies `/api/*` to the backend
  container)
- Cloudflare tunnel: see logs for the public URL —
  `docker compose logs cloudflared`

This stack runs on host ports 8000/8080, so it can run alongside local
`npm run dev` (5173) — just don't also bind local `uvicorn` to host port
8000 at the same time.

## Getting a public URL

The official `cloudflare/cloudflared` image is distroless (no shell
inside), so the two modes are implemented as two separate Compose
services (`cloudflared-quick` / `cloudflared-named`) gated by Compose
**profiles**, selected via the `COMPOSE_PROFILES` variable in `.env`
(Compose reads this automatically — no extra CLI flags needed).

### Option A — Quick tunnel (zero setup, unstable URL) — default

`.env` ships with `COMPOSE_PROFILES=quick` and a blank
`CLOUDFLARE_TUNNEL_TOKEN`. On `docker compose up`, the `cloudflared-quick`
service starts an anonymous "quick tunnel" and prints a random
`https://<random-words>.trycloudflare.com` URL in its logs:

```bash
docker compose logs cloudflared-quick | grep trycloudflare
```

This URL works immediately but **changes every time the container
restarts** — fine for a one-off test, not for a link you want to keep
sharing.

### Option B — Named tunnel (stable URL, requires a Cloudflare account)

1. Go to the Cloudflare Zero Trust dashboard -> **Networks -> Tunnels ->
   Create a tunnel**.
2. Choose the **Docker** connector type. Cloudflare shows a sample
   `docker run` command containing a long `--token <TOKEN>` argument —
   copy just the token value.
3. In `.env`, set `CLOUDFLARE_TUNNEL_TOKEN=<your token>` and change
   `COMPOSE_PROFILES=named`.
4. In the same tunnel setup flow, add a **Public Hostname** pointing at
   `http://frontend:80` (the compose service name/port — cloudflared
   resolves it over the compose network, not localhost).
5. Restart the stack: `docker compose up -d`.
6. The tunnel is now available at the hostname you chose in step 4
   (e.g. `https://dashboard.yourdomain.com`), and it survives container
   restarts because the tunnel identity lives in the token, not in
   anything generated locally.

This step requires action in your own Cloudflare account (creating the
tunnel, choosing a hostname) that can't be done on your behalf — steps
1-4 above are the part you need to do yourself.

## Data persistence

The SQLite DB (`app/data/app.db` inside the backend container) is stored
in the named volume `backend-data`, so it survives `docker compose down`
/ `docker compose up` cycles. To fully reset it:

```bash
docker compose down
docker volume rm dashboard_app_backend-data   # name may vary — check `docker volume ls`
docker compose up -d
```

## Updating the source Excel data files

The 3 source data files live at `backend/data/` on your machine:

- `DEPT - Master Data(Sheet1).xlsx` — employee roster
- `UTILIZATION DATA SHEET.xlsx` — weekly time-booking data
- `PowerBI_Ready_Utilization_May_2026.xlsx` — utilization ground truth

**This is the one and only place to drop updated files, whether you're
running Docker or local dev — both read from this exact folder.**

- Local dev (`uvicorn`/`npm run dev`): picks up a new file the next time
  the backend process restarts (it caches the loaded data in memory at
  startup, not per-request — see `backend/app/services/data_loader.py`).
- Docker: `backend/data/` is bind-mounted straight into the backend
  container (`docker-compose.yml`'s `./backend/data:/app/data`), so a
  file dropped here is immediately visible inside the container too —
  **but the running backend process still needs a restart to pick it up**,
  same as local dev, since it's cached in memory:

```bash
docker compose restart backend
```

You do **NOT** need to rebuild the image (`docker compose build`) just
for a data file change — restarting the container is enough, since the
file lives on a bind mount now, not baked into the image at build time.

**Filenames must match exactly** (including the space/parentheses in
`DEPT - Master Data(Sheet1).xlsx` and `UTILIZATION DATA SHEET.xlsx`) —
the backend's path constants in `roster_metrics.py`/`booking_metrics.py`
look for these exact names. If you rename a file when updating it,
either match the existing name or update those path constants too.

After updating, it's worth re-running the backend test suite
(`cd backend && python -m pytest -q`) — several tests pin exact values
(row counts, name matches, computed KPIs) against the real files, so a
genuine data change may need those regression values updated, and a
test failure here is a fast way to catch it.

## Rebuilding after code changes

```bash
docker compose build backend   # or frontend
docker compose up -d
```
