import { ApiError } from './types'
import { RefreshRequest, RefreshResponse } from './types'

const API_BASE_URL = '/api/v1'

// Token storage
const TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

/**
 * Refresh the access token using the refresh token.
 * Returns true if successful, false otherwise.
 */
async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    return false
  }
  try {
    const response = await post<RefreshResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    } as RefreshRequest, { skipAuth: true })
    // Update tokens
    setTokens(response.access_token, response.refresh_token)
    return true
  } catch (err) {
    // Refresh failed
    clearTokens()
    return false
  }
}

// Error class that includes the API error code
export class ApiClientError extends Error {
  constructor(
    public code: string,
    message: string,
    public field?: string
  ) {
    super(message)
    this.name = 'ApiClientError'
  }
}

interface FetchOptions extends RequestInit {
  skipAuth?: boolean
}

/**
 * Core fetch wrapper that:
 * - Attaches the Authorization header when a token exists
 * - Unwraps the error envelope and surfaces error.code
 * - Handles JSON parsing
 * - Implements refresh-on-401 (once)
 */
async function apiFetch<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const { skipAuth = false, ...fetchOptions } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  // Copy existing headers
  if (fetchOptions.headers) {
    const existingHeaders = fetchOptions.headers as Record<string, string>
    Object.assign(headers, existingHeaders)
  }

  // Attach bearer token if available and not skipped
  const token = getAccessToken()
  if (token && !skipAuth) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const url = `${API_BASE_URL}${endpoint}`

  const response = await fetch(url, {
    ...fetchOptions,
    headers,
  })

  // Handle error responses
  if (!response.ok) {
    // If we get a 401 and haven't tried refreshing yet, attempt to refresh token
    if (response.status === 401 && !skipAuth) {
      const refreshSuccessful = await refreshAccessToken()
      if (refreshSuccessful) {
        // Retry the original request with the new token
        return apiFetch<T>(endpoint, options)
      }
      // If refresh failed, fall through to throw error
    }
    
    let errorData: ApiError
    try {
      errorData = await response.json()
    } catch {
      // If JSON parsing fails, construct a generic error
      throw new ApiClientError(
        'UNKNOWN_ERROR',
        `Request failed with status ${response.status}`
      )
    }

    // Throw an error with the code exposed
    throw new ApiClientError(errorData.code, errorData.message, errorData.field)
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  // Parse and return JSON response
  return response.json()
}

/**
 * GET request
 */
export async function get<T>(endpoint: string, options?: FetchOptions): Promise<T> {
  return apiFetch<T>(endpoint, { ...options, method: 'GET' })
}

/**
 * POST request
 */
export async function post<T>(
  endpoint: string,
  body?: unknown,
  options?: FetchOptions
): Promise<T> {
  return apiFetch<T>(endpoint, {
    ...options,
    method: 'POST',
    body: body ? JSON.stringify(body) : undefined,
  })
}

/**
 * PATCH request
 */
export async function patch<T>(
  endpoint: string,
  body?: unknown,
  options?: FetchOptions
): Promise<T> {
  return apiFetch<T>(endpoint, {
    ...options,
    method: 'PATCH',
    body: body ? JSON.stringify(body) : undefined,
  })
}

/**
 * DELETE request
 */
export async function del<T>(endpoint: string, options?: FetchOptions): Promise<T> {
  return apiFetch<T>(endpoint, { ...options, method: 'DELETE' })
}

// Export the core apiFetch for advanced use cases
export { apiFetch }
