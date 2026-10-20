# Weather-Aware Truck Routing

A React + Django demo that compares Valhalla truck routes using Open-Meteo
forecast risk at route checkpoints. Submitted locations are geocoded with
Nominatim and displayed with MapLibre/OpenFreeMap.

## Local development

The backend uses the ignored `backend/db.sqlite3` locally when `DATABASE_URL`
is unset. Hosted environments require PostgreSQL and cannot fall back to
SQLite.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`. Run checks with:

```bash
cd backend && python manage.py test
cd frontend && npm run lint && npm run build
```

After `neon deploy`, Django loads the ignored root `.env.local` automatically.
Application requests use Neon's pooled `DATABASE_URL`; `manage.py migrate`
prefers `DATABASE_URL_UNPOOLED` when it is available. `GET /ready/` performs a
database round trip, while `GET /health/` remains a database-free liveness check.

## Deploy to Neon and Render

`render.yaml` creates a Free Django Web Service and Free React Static Site. It
pins Python `3.14.3` and Node `24.22.1`. The database is an external Neon Free
PostgreSQL database; no Render database is created.

1. Use the linked Neon production branch. Run `neon deploy` after changing
   `neon.ts`; it also refreshes the ignored `.env.local` connection values.
2. In Render, create a Blueprint from this repository and confirm the API plan
   is **Free**. Render will request the values marked `sync: false` below.
3. Deploy the API, then check `https://<api-host>/health/`. A successful response
   is only process liveness; it does not check Neon or external providers.
4. Set the frontend's `VITE_API_BASE_URL` to the API's HTTPS origin and deploy
   the static site.
5. If Render assigns different hostnames, update the matching environment
   values and redeploy.

### API environment

| Name | Value |
| --- | --- |
| `DATABASE_URL` | Neon pooled PostgreSQL URL (secret) |
| `DATABASE_URL_UNPOOLED` | Neon direct PostgreSQL URL for migrations (secret) |
| `DJANGO_SECRET_KEY` | Render-generated secret |
| `ALLOWED_HOSTS` | API hostname without `https://` |
| `FRONTEND_ORIGINS` | Exact frontend HTTPS origin, no path |
| `PROVIDER_USER_AGENT` | Identifying app/contact string for Nominatim |
| `VALHALLA_CLIENT_ID` | Unique public identifier for this demo |

`DJANGO_ENV=production`, `DEBUG=0`, `PYTHON_VERSION=3.14.3`, and the migration,
static collection, Gunicorn, and health-check commands are already defined in
`render.yaml`. Startup runs migrations before serving traffic and fails if a
required production setting is missing.

Optional overrides: `NOMINATIM_BASE_URL`, `VALHALLA_ROUTE_URL`,
`OPEN_METEO_BASE_URL`, and `GEOCODING_CACHE_SECONDS`.

### Frontend environment

| Name | Value |
| --- | --- |
| `VITE_API_BASE_URL` | Exact API HTTPS origin, no trailing slash |

`NODE_VERSION=24.22.1`, `npm ci && npm run build`, the `dist` publish directory,
and the SPA rewrite are defined in `render.yaml`. All `VITE_*` values are public;
never put credentials in them.

## Demo limitations

- Render Free sleeps when idle. The frontend performs bounded `/health/` wake-up
  retries before submitting exactly one trip POST. A timed-out POST may still
  finish on the server and is never automatically resubmitted.
- Nominatim is submit-triggered and cached. Every attempt uses a thread-safe
  one-request-per-second limiter. It is process-local and depends on the single
  Gunicorn worker configured in `render.yaml`; redesign it before scaling out.
- Valhalla's public server is fair-use/demo infrastructure. Open-Meteo's free
  API is non-commercial and quota-limited. OpenFreeMap and all providers have
  no uptime guarantee; required attribution remains visible in the app.
- Render's filesystem is ephemeral. Neon Free storage/compute/egress are finite.

For a bad code deploy, use Render's previous-deploy rollback. Code rollback does
not reverse database migrations; use Neon's restore/branch tools for data or
schema recovery.

## Optional SQLite data import

Fresh Neon data is the default. The local SQLite database is ignored and left
untouched. To import existing trips from your machine:

```bash
cd backend
DJANGO_ENV=development python manage.py dumpdata trips --indent 2 --output /tmp/truck-router-trips.json
DJANGO_ENV=development DATABASE_URL="$TRUCK_NEON_DATABASE_URL" python manage.py migrate
DJANGO_ENV=development DATABASE_URL="$TRUCK_NEON_DATABASE_URL" python manage.py loaddata /tmp/truck-router-trips.json
```

Keep the export and Neon URL out of Git. The main API entry point is
`POST /api/trips/`; departure times are converted to UTC while preserving the
user's local instant, including IST.
