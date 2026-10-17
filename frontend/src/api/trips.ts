import { postJson } from './http'
import type { Severity } from './types'

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
}

export interface TripRoute {
  provider_route_index: number
  coords: [number, number][]
  distance_mi: number
  travel_time_hr: number
  segment_count: number
  checkpoints: TripCheckpoint[]
}

export interface TripResult {
  id: number
  start: TripEndpoint
  end: TripEndpoint
  load_lb: number
  depart_at: string
  sample_miles: number
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
  return postJson<TripResult>('/api/trips/', request)
}
