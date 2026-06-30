/**
 * The single network seam. Every API call goes through `request()` so:
 *  - the in-memory JWT is attached as `Authorization: Bearer …` (FRONTEND-2),
 *  - errors normalize to `ApiError` (status + parsed body) for consistent UI handling,
 *  - a 401 notifies the auth layer (refresh/logout) — defense-in-depth; the server is authoritative.
 * When `VITE_USE_MOCKS=true`, MSW intercepts these same fetches, so flipping mock↔real is one flag.
 */
import { env } from './env'
import { getAccessToken, notifyUnauthorized } from './authToken'

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown
  constructor(status: number, message: string, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Record<string, string | number | boolean | undefined | null>
  body?: unknown
  signal?: AbortSignal
  /** Override Accept handling for text endpoints (e.g. GET /metrics → Prometheus text). */
  responseType?: 'json' | 'text'
  headers?: Record<string, string>
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const base = env.apiBaseUrl.replace(/\/$/, '')
  const url = new URL(`${base}${path}`, window.location.origin)
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
    }
  }
  return url.toString()
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, body, signal, responseType = 'json', headers = {} } = options
  const token = getAccessToken()

  const init: RequestInit = {
    method,
    signal,
    headers: {
      Accept: responseType === 'text' ? 'text/plain' : 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  }

  let res: Response
  try {
    res = await fetch(buildUrl(path, query), init)
  } catch (cause) {
    throw new ApiError(0, `Network error calling ${method} ${path}`, cause)
  }

  if (res.status === 401) {
    notifyUnauthorized()
  }

  if (!res.ok) {
    const errBody = await safeParse(res)
    const message =
      (isRecord(errBody) && typeof errBody.detail === 'string' && errBody.detail) ||
      (isRecord(errBody) && typeof errBody.message === 'string' && errBody.message) ||
      `${method} ${path} failed (${res.status})`
    throw new ApiError(res.status, message, errBody)
  }

  if (res.status === 204) return undefined as T
  if (responseType === 'text') return (await res.text()) as T
  return (await res.json()) as T
}

async function safeParse(res: Response): Promise<unknown> {
  const text = await res.text().catch(() => '')
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null
}
