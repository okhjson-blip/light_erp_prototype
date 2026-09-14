import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  apiGet,
  apiPost,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  registerForceLogout,
  setTokens,
} from './api'
import type { LoginResponse, User } from './types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  ssoError: string | null
  login: (password: string) => Promise<void>
  logout: () => Promise<void>
  hasRole: (...roles: string[]) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    registerForceLogout(() => setUser(null))

    async function restoreSession() {
      try {
        if (!getAccessToken()) return
        const me = await apiGet<User>('/api/auth/me')
        setUser(me)
      } catch {
        setUser(null)
        clearTokens()
      } finally {
        setLoading(false)
      }
    }
    restoreSession()
  }, [])

  async function login(password: string) {
    const session = await apiPost<LoginResponse>('/api/auth/login', { password })
    setTokens(session)
    setUser(session.user)
  }

  async function logout() {
    const refreshToken = getRefreshToken()
    try {
      if (refreshToken) {
        await apiPost('/api/auth/logout', { refresh_token: refreshToken })
      }
    } catch {
      // 서버 호출이 실패해도 로컬 세션은 반드시 정리한다.
    }
    clearTokens()
    setUser(null)
  }

  // Light ERP Prototype: 역할/페이지별 권한 구분 없음 — 로그인만 하면 전체 기능 사용
  function hasRole(..._roles: string[]) {
    return !!user
  }

  return (
    <AuthContext.Provider value={{ user, loading, ssoError: null, login, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth는 AuthProvider 내부에서만 사용할 수 있습니다')
  return ctx
}
