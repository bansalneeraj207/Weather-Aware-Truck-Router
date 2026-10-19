/** Shared fetch helpers for the routing API. */

import { ApiError } from './types'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

interface RequestOptions {
  timeoutMs: number
}

export async function postJson<T>(
  path: string,
  body: unknown,
  options: RequestOptions,
): Promise<T> {
  return requestJson<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, options)
}

export async function getJson<T>(
  path: string,
  options: RequestOptions,
): Promise<T> {
  return requestJson<T>(path, {}, options)
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  { timeoutMs }: RequestOptions,
): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
    })
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ApiError('The routing API did not respond in time.', 0, error, 'TIMEOUT')
    }
    throw new ApiError('Could not reach the routing API.', 0, error, 'NETWORK')
  } finally {
    window.clearTimeout(timeout)
  }

  let data: unknown
  try {
    data = await response.json()
  } catch (error) {
    throw new ApiError(
      'The routing API returned an unreadable response.',
      response.status,
      error,
      'INVALID_RESPONSE',
    )
  }
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
