/** Types shared across the trip planner API modules. */

export type SeverityName =
  | 'LOW'
  | 'MODERATE'
  | 'HIGH'
  | 'SEVERE'
  | 'NO_TRAVEL'

/** UNKNOWN is represented as null, never LOW. */
export type Severity = SeverityName | null

export type ApiErrorCode = 'NETWORK' | 'TIMEOUT' | 'INVALID_RESPONSE'

export class ApiError extends Error {
  readonly status: number
  readonly details?: unknown
  readonly code?: ApiErrorCode

  constructor(
    message: string,
    status: number,
    details?: unknown,
    code?: ApiErrorCode,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
    this.code = code
  }
}
