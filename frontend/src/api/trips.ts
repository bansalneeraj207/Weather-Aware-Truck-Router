import { postJson } from './http'
import type { Severity } from './types'

export interface TripEndpoint {
  label: string
  lat: number
  lon: number
}


export interface TripResult {
  id: number
  start: TripEndpoint
  end: TripEndpoint
  load_lb: number
  depart_at: string
  sample_miles: number
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
