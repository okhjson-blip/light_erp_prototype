import type { AuthTokens, LoginResponse } from './types'

/* API 클라이언트 — 백엔드의 access+refresh 회전 계약(app/auth.py, v6)을 그대로 재현한다.
   401 수신 시 자동으로 /api/auth/refresh를 시도해 회전된 새 토큰으로 원요청을 1회 재시도하고,
   그마저 실패하면 강제 로그아웃 콜백을 호출한다(task-plan-frontend-react.md 참고). */

const ACCESS_KEY = 'erp_access_token'
const REFRESH_KEY = 'erp_refresh_token'

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY)
}

export function setTokens(tokens: AuthTokens) {
  localStorage.setItem(ACCESS_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

let onForceLogout: (() => void) | null = null

// AuthProvider가 등록한다 — api.ts가 auth-context를 직접 import하지 않도록 의존성을 역전시킨다.
export function registerForceLogout(fn: () => void) {
  onForceLogout = fn
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false
  const res = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!res.ok) return false
  const data = await res.json()
  setTokens(data)
  return true
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const doFetch = () => {
    const token = getAccessToken()
    return fetch(path, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
  }

  let res = await doFetch()
  if (res.status === 401) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      res = await doFetch()
    }
    if (res.status === 401) {
      clearTokens()
      onForceLogout?.()
      throw new ApiError(401, '로그인이 필요합니다')
    }
  }

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new ApiError(res.status, data.detail || '요청 실패')
  }
  return data as T
}

export function apiGet<T>(path: string) {
  return apiFetch<T>(path)
}

export function apiPost<T>(path: string, body?: unknown) {
  return apiFetch<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
}

export async function exchangeSsoToken(oidcAccessToken: string) {
  const res = await fetch('/api/auth/sso', {
    method: 'POST',
    headers: { Authorization: `Bearer ${oidcAccessToken}` },
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(res.status, data.detail || 'SSO 로그인에 실패했습니다')
  return data as LoginResponse
}
