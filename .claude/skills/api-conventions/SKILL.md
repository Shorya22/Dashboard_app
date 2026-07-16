---
name: api-conventions
description: Use whenever creating or editing FastAPI routes, models, auth logic, or the data-access layer that reads Excel/Power BI/database data. Covers endpoint shape, auth flow, error format, and how the data layer should be structured so switching from Excel to a database later doesn't touch the API contract.
---

# Backend API conventions

## Project layout

```
backend/
  app/
    main.py
    api/          # route handlers only — no business logic here
    core/          # config, security/JWT helpers
    models/        # Pydantic request/response models
    services/      # business logic + data access, called by api/
    data/
      sample/      # masked sample Excel files for local dev
  alembic/         # migrations, once a real DB exists
```

Route handlers in `api/` should be thin: parse the request, call a
function in `services/`, return the response model. All actual logic
(reading Excel, aggregating, querying) lives in `services/` so it can be
tested and swapped independently of the HTTP layer.

## The Excel/DB swap boundary

Every data-access function in `services/` (e.g. `get_revenue_by_month()`)
must be swappable from "reads Excel with pandas" to "queries Postgres"
without changing its signature or return shape. Never let a route handler
call `pandas.read_excel` directly — always through a `services/` function.

## Auth

- JWT access token, short-lived (~15 min)
- Refresh token in an httpOnly, Secure cookie — never returned in JSON,
  never stored in localStorage
- Endpoints: `POST /api/auth/login`, `POST /api/auth/refresh`,
  `POST /api/auth/logout`
- Every protected route depends on a shared `get_current_user` dependency
  that validates the access token — don't duplicate token-checking logic
  per route
- Include a `role` field on the user model from the start (`admin` /
  `viewer`), even before role-based restrictions are enforced anywhere

## Response and error format

- Every endpoint has an explicit Pydantic response model — no returning
  raw dicts
- List endpoints are paginated: accept `limit`/`offset` query params,
  return `{ "items": [...], "total": N }`
- Errors return a consistent shape:
  `{ "detail": "human-readable message" }` with the appropriate HTTP
  status code — never leak a raw stack trace or exception string to the
  client
- API is versioned under `/api/v1/...`

## Logging

Use Python's `logging` module (not `print`), with a request ID attached
to each log line so a single request can be traced through the logs.
