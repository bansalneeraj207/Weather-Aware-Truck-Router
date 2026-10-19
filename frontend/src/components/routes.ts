/** Shared view of the route options shown on the cards and the map. */

import type { TripResult, TripRoute } from '../api/trips'

export const MAX_SHOWN_ROUTES = 3

export function etaLabel(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  })
}

export function shownRoutes(routes: TripRoute[]): TripRoute[] {
  return routes.slice(0, MAX_SHOWN_ROUTES)
}

/** Prefer the recommendation; fall back to the first returned alternative. */
export function defaultSelectedRouteIndex(routes: TripRoute[]): number | null {
  const visible = shownRoutes(routes)
  return visible.find((route) => route.is_recommended)?.provider_route_index
    ?? visible[0]?.provider_route_index
    ?? null
}

export function checkpointFeatureCollection(
  trip: TripResult,
  selectedRouteIndex: number,
  forecastHour: number | null = null,
) {
  const route = shownRoutes(trip.routes).find(
    (candidate) => candidate.provider_route_index === selectedRouteIndex,
  )
  const checkpoints = route?.checkpoints ?? []
  const forecastPoints = forecastHour === null
    ? []
    : forecastPointsForRoute(trip, selectedRouteIndex)
  return {
    type: 'FeatureCollection' as const,
    features: checkpoints.map((checkpoint, index) => {
      const forecastPoint = forecastHour === null ? null : forecastPoints[index]
      const forecastSeverity = forecastHour === null
        ? null
        : forecastPoint?.severity[forecastHour] ?? null
      return {
        type: 'Feature' as const,
        properties: {
          wind_mph: forecastPoint === null
            ? checkpoint.wind_mph
            : forecastPoint.wind_mph[forecastHour as number] ?? null,
          rain_in_hr: forecastPoint === null
            ? checkpoint.rain_in_hr ?? null
            : forecastPoint.rain_in_hr[forecastHour as number] ?? null,
          snow_in_hr: forecastPoint === null
            ? checkpoint.snow_in_hr ?? null
            : forecastPoint.snow_in_hr[forecastHour as number] ?? null,
          eta_label: etaLabel(checkpoint.eta),
          forecast_label: forecastHour === null
            ? null
            : forecastTimeLabel(trip.depart_at, forecastHour),
          weather_mode: forecastHour === null ? 'ARRIVAL' : 'FORECAST',
          severity: forecastSeverity ?? checkpoint.final_severity ?? 'UNKNOWN',
        },
        geometry: {
          type: 'Point' as const,
          coordinates: [checkpoint.lon, checkpoint.lat] as [number, number],
        },
      }
    }),
  }
}

function forecastTimeLabel(departAt: string, hour: number): string {
  const departure = new Date(departAt)
  if (Number.isNaN(departure.getTime())) return `Forecast + ${hour} hours`

  return new Date(departure.getTime() + hour * 60 * 60_000).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  })
}

function forecastPointsForRoute(trip: TripResult, selectedRouteIndex: number) {
  let offset = 0
  for (const route of shownRoutes(trip.routes)) {
    const count = route.checkpoints.length
    if (route.provider_route_index === selectedRouteIndex) {
      return trip.heatmap.points.slice(offset, offset + count)
    }
    offset += count
  }
  return []
}

/** Forecast-only overlay. It never changes ETA-based route assessments. */
export function heatmapFeatureCollection(
  trip: TripResult,
  selectedRouteIndex: number,
  hour: number,
) {
  return {
    type: 'FeatureCollection' as const,
    features: forecastPointsForRoute(trip, selectedRouteIndex).map((point) => ({
      type: 'Feature' as const,
      properties: { severity: point.severity[hour] ?? 'UNKNOWN' },
      geometry: {
        type: 'Point' as const,
        coordinates: [point.lon, point.lat] as [number, number],
      },
    })),
  }
}

export function routeFeatureCollection(routes: TripRoute[], selectedRouteIndex: number) {
  const drawable = shownRoutes(routes).filter((route) => route.geometry.length >= 2)
  const ordered = [
    ...drawable.filter((route) => route.provider_route_index !== selectedRouteIndex),
    ...drawable.filter((route) => route.provider_route_index === selectedRouteIndex),
  ]
  return {
    type: 'FeatureCollection' as const,
    features: ordered.map((route) => ({
      type: 'Feature' as const,
      properties: { selected: route.provider_route_index === selectedRouteIndex ? 1 : 0 },
      geometry: { type: 'LineString' as const, coordinates: route.geometry },
    })),
  }
}
