# Running Dashboard_app with Docker Compose

This containerizes the backend (FastAPI) and frontend (React/Vite built
static bundle, served by nginx).

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

This stack runs on host ports 8000/8080, so it can run alongside local
`npm run dev` (5173) — just don't also bind local `uvicorn` to host port
8000 at the same time.

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
