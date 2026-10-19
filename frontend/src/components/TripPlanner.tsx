/** Trip planner: origin, destination, departure, load, and route results. */

import { useState } from 'react'
import { createTrip } from '../api/trips'
import type { TripResult } from '../api/trips'
import { ApiError } from '../api/types'
import { RouteMap } from './RouteMap'
import { defaultSelectedRouteIndex, shownRoutes } from './routes'
import { RouteCard } from './RouteCard'

const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

function localDepartureValue(date = new Date()): string {
  // datetime-local stores a wall-clock value. Offset it before slicing the ISO
  // string so the input displays the user's local time, not UTC.
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}


export default function TripPlanner() {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [depart, setDepart] = useState(localDepartureValue)
  const [sampleMiles, setSampleMiles] = useState<10 | 25 | 50>(25)
  const [load, setLoad] = useState('40000')
  const [trip, setTrip] = useState<TripResult | null>(null)
  const [selectedRouteIndex, setSelectedRouteIndex] = useState<number | null>(null)
  const [forecastHour, setForecastHour] = useState(0)
  const [showForecastOverlay, setShowForecastOverlay] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)
    const departure = new Date(depart)
    const loadWeight = Number(load)
    if (Number.isNaN(departure.getTime())) {
      setError('Choose a valid local departure date and time.')
      setPending(false)
      return
    }
    if (!Number.isFinite(loadWeight) || loadWeight <= 0) {
      setError('Enter a load weight greater than 0 lb.')
      setPending(false)
      return
    }
    try {
      const result = await createTrip({
        start: start.trim(),
        end: end.trim(),
        load_lb: loadWeight,
        // Date parses datetime-local in the browser's timezone, then sends the
        // matching UTC instant to the API.
        depart_at: departure.toISOString(),
        sample_miles: sampleMiles,
      })
      setTrip(result)
      setSelectedRouteIndex(0)
      setForecastHour(0)
      setShowForecastOverlay(false)
    } catch (err) {
      setTrip(null)
      setSelectedRouteIndex(null)
      setError(err instanceof ApiError ? err.message : 'Trip planning failed.')
    } finally {
      setPending(false)
    }
  }

  return (    
    <section className="panel">
      <h2>Plan a trip</h2>
      <form onSubmit={handleSubmit} className="planner-form">
        <label className="field">
          <span>Start</span>
          <input
            value={start}
            placeholder="Chicago, IL"
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Destination</span>
          <input
            value={end}
            placeholder="Des Moines, IA"
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Departure ({timeZone})</span>
          <input
            type="datetime-local"
            value={depart}
            onChange={(e) => setDepart(e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Sample every</span>
          
          <select
            value={sampleMiles}
            onChange={(e) => setSampleMiles(Number(e.target.value) as 10 | 25 | 50)}
          >
            <option value={10}>10 miles</option>
            <option value={25}>25 miles</option>
            <option value={50}>50 miles</option>
          </select>
        </label>
        <label className="field">
          <span>Load (lb)</span>
          <input
            value={load}
            inputMode="decimal"
            onChange={(e) => setLoad(e.target.value)}
          />
        </label>
        <button type="submit" disabled={pending || !start.trim() || !end.trim()}>
          {pending ? 'Planning...' : 'Plan trip'}
        </button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      
      {trip && (
        <div className="planner-results">
          <div className="planner-summary">
            <p className="final">
              {trip.recommended_route_index !== null
                ? `Recommended: Option ${trip.recommended_route_index + 1} has the lowest weather risk.`
                : 'No route can be recommended for this departure.'}
            </p>
            {trip.routing_segments > 1 && (
              <p className="routing-notice" role="status">
                This long-haul route is shown as {trip.routing_segments} connected legs because the routing provider has a per-request distance limit. Weather risk covers the complete combined trip; alternative long-haul routes are not available for this result.
              </p>
            )}
            {trip.weather_forecast_partial ? (
              <p className="warning" role="status">
                Forecast coverage is partial; route segments beyond the forecast window are shown as Unknown.
              </p>
            ) : trip.routes.some((route) => route.metrics.unknown_miles !== '0') && (
              <p className="warning" role="status">
                Some weather data is unavailable.
              </p>
            )}
          </div>
          <div className="planner-body">
            <div className="map-column">
              <div className="map-toolbar">
                <strong>Route map</strong>
                <label>
                  <input
                    type="checkbox"
                    checked={showForecastOverlay}
                    onChange={(event) => setShowForecastOverlay(event.target.checked)}
                  />
                  Forecast heatmap
                </label>
              </div>
              <RouteMap
                key={trip.id}
                trip={trip}
                selectedRouteIndex={
                  selectedRouteIndex ?? defaultSelectedRouteIndex(trip.routes) ?? 0
                }
                forecastHour={forecastHour}
                showForecastOverlay={showForecastOverlay}
              />

            </div>
            <div className="route-cards">
              {shownRoutes(trip.routes).map((route) => (
                <RouteCard
                  key={route.provider_route_index}
                  route={route}
                  departAt={trip.depart_at}
                  weatherUnavailable={trip.status === 'WEATHER_FORECAST_UNAVAILABLE'}
                  selected={selectedRouteIndex === route.provider_route_index}
                  onSelect={() => setSelectedRouteIndex(route.provider_route_index)}
                />
              ))}
            </div>
          </div>
          <div className="legend">
            <span className="legend-item">
              <span className="dot" style={{ background: '#16a34a' }} /> Low
            </span>
            <span className="legend-item">
              <span className="dot" style={{ background: '#ca8a04' }} /> Moderate
            </span>
            <span className="legend-item">
              <span className="dot" style={{ background: '#ea580c' }} /> High
            </span>
            <span className="legend-item">
              <span className="dot" style={{ background: '#dc2626' }} /> Severe
            </span>
            <span className="legend-item">
              <span className="dot" style={{ background: '#7f1d1d' }} /> No Travel
            </span>
            <span className="legend-item">
              <span className="dot" style={{ background: '#9ca3af' }} /> Unknown
            </span>
          </div>
          <p className="wind-note">
            Click a checkpoint for its arrival-time weather details.
          </p>
        </div>
      )}
    </section>
  )
}
