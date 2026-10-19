# Frontend

React 19 and Vite 8 frontend for the Weather-Aware Truck Router.

```bash
npm ci
npm run dev
npm run lint
npm run build
```

Local development uses Vite's `/api` and `/health` proxy to Django on
`127.0.0.1:8000`. Hosted builds must set the public, build-time
`VITE_API_BASE_URL` to the Django API's HTTPS origin. Do not put secrets in
`VITE_*` variables.

Render settings are defined in the repository's `render.yaml`: Node 24.22.1,
build command `npm ci && npm run build`, publish directory `dist`, and an SPA
rewrite from `/*` to `/index.html`. See the root README for the full deployment
order and environment-variable inventory.
