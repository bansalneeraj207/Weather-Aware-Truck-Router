/** Trip planner: origin, destination, departure, load, and route results. */

import { useState } from 'react'
import { createTrip } from '../api/trips'
import type { TripResult } from '../api/trips'
import { ApiError } from '../api/types'
import RouteMap from './RouteMap'

const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

function localDepartureValue(date = new Date()): string {
  // datetime-local stores a wall-clock value. Offset it before slicing the ISO
  // string so the input displays the user's local time, not UTC.
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}


export default function TripPlanner() {
  const [start, setStart] = useState('Mumbai, India')
  const [end, setEnd] = useState('Delhi, India')
  const [depart, setDepart] = useState(localDepartureValue)
  const [sampleMiles, setSampleMiles] = useState<10 | 25 | 50>(25)
  const [load, setLoad] = useState('40000')
  const [trip, setTrip] = useState<TripResult | null>(null)
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
        depart_at: departure.toISOString(),
        sample_miles: sampleMiles,
      })
      setTrip(result)
      console.log(result)
    } catch (err) {
      setTrip(null)
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
        <div>
          <RouteMap trip={trip} />
        </div>
      )}
      
    </section>
  )
}
