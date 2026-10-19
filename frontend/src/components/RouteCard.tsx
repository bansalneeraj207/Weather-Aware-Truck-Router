import type { TripRoute } from '../api/trips'
import { etaLabel } from './routes'

export function RouteCard({
  route,
  departAt,
  weatherUnavailable,
  selected,
  onSelect,
}: {
  route: TripRoute
  departAt: string
  weatherUnavailable: boolean
  selected: boolean
  onSelect: () => void
}) {
  const ineligible = route.rank === null
  const arrival = new Date(new Date(departAt).getTime() + route.travel_time_hr * 3_600_000)
  const riskRows = [
    { label: 'Severe', miles: route.metrics.severe_miles, color: '#dc2626' },
    { label: 'High', miles: route.metrics.high_miles, color: '#ea580c' },
    { label: 'No travel', miles: route.metrics.no_travel_miles, color: '#7f1d1d' },
    { label: 'Unknown', miles: route.metrics.unknown_miles, color: '#9ca3af' },
  ].filter((risk) => Number(risk.miles) > 0)
  return (
    <button
      type="button"
      className={`route-card ${selected ? 'selected' : ''}`}
      onClick={onSelect}
      aria-pressed={selected}
      aria-expanded={selected}
    >
      <div className="route-card-head">
        <strong>
          Option {route.provider_route_index + 1}
          {route.is_recommended ? ' · Recommended' : ''}
        </strong>
        {weatherUnavailable ? (
          <span className="badge severity-unknown">Forecast unavailable</span>
        ) : ineligible ? (
          <span className="badge severity-no-travel">Ineligible</span>
        ) : (
          <span className="rank">#{route.rank}</span>
        )}
      </div>
      <dl className="route-metrics">
        <div><dt>Distance</dt><dd>{route.distance_mi.toFixed(1)} mi</dd></div>
        <div><dt>Travel time</dt><dd>{route.travel_time_hr.toFixed(1)} hr</dd></div>
        <div><dt>ETA</dt><dd>{etaLabel(arrival.toISOString())}</dd></div>
        {selected && (
          riskRows.length === 0 ? (
            <div><dt>Weather risk</dt><dd>No significant risk</dd></div>
          ) : (
            <>
              {riskRows.map((risk) => (
                <div key={risk.label}>
                  <dt><span className="dot" style={{ background: risk.color }} /> {risk.label}</dt>
                  <dd>{risk.miles} mi</dd>
                </div>
              ))}
              <div><dt>Average risk</dt><dd>{route.metrics.average_risk ?? '—'}</dd></div>
            </>
          )
        )}
      </dl>
    </button>
  )
}
