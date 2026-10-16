/** Types shared across the trip planner API modules. */

export type SeverityName =
  | 'LOW'
  | 'MODERATE'
  | 'HIGH'
  | 'SEVERE'
  | 'NO_TRAVEL'

/** UNKNOWN is represented as null, never LOW. */
export type Severity = SeverityName | null

export class ApiError extends Error {
  readonly status: number
  readonly details?: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}
