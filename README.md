# Weather-Aware Truck Routing

A React and Django app for comparing truck routes against forecast weather.

Enter an origin, destination, departure time, load, and checkpoint spacing.
The app gets up to three driving routes, checks the forecast at the truck's
estimated arrival time at each checkpoint, then recommends the safer option.

## Run locally

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server forwards API requests to Django. Run `python manage.py test`
in `backend` and `npm test` in `frontend`.

---

## How it works

- Geocoding: Nominatim
- Routing: Valhalla truck routes
- Weather: Open-Meteo hourly forecast
- Map: MapLibre with OpenFreeMap tiles

Routes are sampled every 10, 25, or 50 miles. Every checkpoint uses its own
ETA, not the departure-time weather. The selected route shows its checkpoints
and ETAs when you zoom in. The optional heatmap is a separate 48-hour forecast
view and does not change the recommendation.

## Risk rules

| Condition | Low | Moderate | High | Severe | No travel |
| --- | --- | --- | --- | --- | --- |
| Wind | <25 mph | 25–34 | 35–44 | 45–54 | ≥55 mph |
| Rain | <0.10 in/hr | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow | <0.5 in/hr | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

Load changes wind risk:

- 55 mph or more: no travel for every load.
- 45–54 mph with more than 30,000 lb: no travel.
- 35–44 mph with more than 40,000 lb: severe.

Routes are ordered by severe miles, high miles, average risk, and travel time.
Known no-travel segments make a route ineligible. Missing weather remains
unknown; it is never treated as safe. If a trip is outside the forecast window,
the app still shows the routes but does not recommend one.

## API

`POST /api/trips/`

```json
{
  "start": "Reykjavík, Iceland",
  "end": "Ísafjörður, Iceland",
  "depart_at": "2026-10-18T02:00:00Z",
  "load_lb": 25000,
  "sample_miles": 25
}
```
