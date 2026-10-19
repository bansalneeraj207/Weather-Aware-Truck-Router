import { getJson, postJson } from './http'
import { ApiError } from './types'
import type { Severity } from './types'

const HEALTH_ATTEMPTS = 2
const HEALTH_TIMEOUT_MS = 75_000
const HEALTH_RETRY_DELAY_MS = 1_500
const TRIP_ANALYSIS_TIMEOUT_MS = 300_000

export interface TripEndpoint {
  label: string
  lat: number
  lon: number
}

export interface TripCheckpoint {
  lat: number
  lon: number
  distance_mi: number
  eta: string
  wind_mph?: number | null
  rain_in_hr?: number | null
  snow_in_hr?: number | null
  final_severity: Severity
  is_complete: boolean
  reason_codes: string[]
}

export interface TripRouteMetrics {
  total_distance_mi: string
  assessed_miles: string
  unknown_miles: string | null
  severe_miles: string
  high_miles: string
  no_travel_miles: string
  average_risk: string | null
}

export interface TripRoute {
  provider_route_index: number
  distance_mi: number
  travel_time_hr: number
  geometry: [number, number][]
  checkpoints: TripCheckpoint[]
  metrics: TripRouteMetrics
  rank: number | null
  is_recommended: boolean
  reason_codes: string[]
  segment_count: number
}

export interface HeatmapPoint {
  lat: number
  lon: number
  severity: (Severity | null)[]
  wind_mph: (number | null)[]
  rain_in_hr: (number | null)[]
  snow_in_hr: (number | null)[]
}

export interface TripResult {
  id: number
  start: TripEndpoint
  end: TripEndpoint
  load_lb: number
  depart_at: string
  sample_miles: number
  heatmap: { hours: number; points: HeatmapPoint[] }
  weather_forecast_partial: boolean
  routing_segments: number
  status: 'RECOMMENDED' | 'NO_ACCEPTABLE_ROUTE' | 'NO_ROUTES' | 'WEATHER_FORECAST_UNAVAILABLE'
  recommended_route_index: number | null
  reason_codes: string[]
  explanations: string[]
  routes: TripRoute[]
}

export interface TripRequest {
  start: string
  end: string
  load_lb: number
  depart_at: string
  sample_miles: 10 | 25 | 50
}

export function createTrip(request: TripRequest): Promise<TripResult> {
  return postJson<TripResult>('/api/trips/', request, {
    timeoutMs: TRIP_ANALYSIS_TIMEOUT_MS,
  })
}

export async function waitForApi(
  onAttempt: (attempt: number, attempts: number) => void,
): Promise<void> {
  let lastError: unknown
  for (let attempt = 1; attempt <= HEALTH_ATTEMPTS; attempt += 1) {
    onAttempt(attempt, HEALTH_ATTEMPTS)
    try {
      const response = await getJson<{ status: string }>('/health/', {
        timeoutMs: HEALTH_TIMEOUT_MS,
      })
      if (response?.status !== 'ok') {
        throw new ApiError(
          'The routing API health response was invalid.',
          0,
          response,
          'INVALID_RESPONSE',
        )
      }
      return
    } catch (error) {
      lastError = error
      if (attempt < HEALTH_ATTEMPTS) {
        await new Promise((resolve) => window.setTimeout(resolve, HEALTH_RETRY_DELAY_MS))
      }
    }
  }
  throw lastError
}
