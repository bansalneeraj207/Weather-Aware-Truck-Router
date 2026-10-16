/** Shared fetch helpers for the routing API. */

import { ApiError } from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Could not reach the routing API.', 0)
  }

  const data = (await response.json().catch(() => null)) as unknown
  if (!response.ok) {
    throw new ApiError(_detail(data, response.status), response.status, data)
  }
  return data as T
}

export async function getJson<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`)
  } catch {
    throw new ApiError('Could not reach the routing API.', 0)
  }

  const data = (await response.json().catch(() => null)) as unknown
  if (!response.ok) {
    throw new ApiError(_detail(data, response.status), response.status, data)
  }
  return data as T
}

function _detail(data: unknown, httpStatus: number): string {
  if (typeof data === 'object' && data !== null && 'detail' in data) {
    return String((data as { detail: unknown }).detail)
  }
  return `Request failed with status ${httpStatus}.`
}
