import { useCallback, useEffect, useState } from 'react'
import {
  clearSession,
  fetchAuthStatus,
  fetchMe,
  getAccessToken,
  getStoredUser,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  subscribeAuth,
  type AuthStatus,
  type AuthUser,
} from '../authApi'
import { setActiveUserId } from '../utils/userScope'

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser())
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  const applyUser = useCallback((next: AuthUser | null) => {
    setUser(next)
    setActiveUserId(next?.id ?? null)
  }, [])

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const st = await fetchAuthStatus()
      setStatus(st)
      const token = getAccessToken()
      if (!token) {
        applyUser(null)
        return
      }
      const me = await fetchMe()
      applyUser(me)
    } catch (e) {
      clearSession()
      applyUser(null)
      setError(e instanceof Error ? e.message : 'Auth check failed')
    } finally {
      setLoading(false)
    }
  }, [applyUser])

  useEffect(() => {
    const stored = getStoredUser()
    setActiveUserId(stored?.id ?? null)
    void refresh()
    return subscribeAuth(() => {
      applyUser(getStoredUser())
    })
  }, [refresh, applyUser])

  const login = async (email: string, password: string) => {
    setError(null)
    const res = await apiLogin(email, password)
    applyUser(res.user)
    return res.user
  }

  const register = async (email: string, password: string) => {
    setError(null)
    const res = await apiRegister(email, password)
    applyUser(res.user)
    setStatus({ has_users: true, allow_register: true })
    return res.user
  }

  const logout = async () => {
    await apiLogout()
    applyUser(null)
  }

  return {
    user,
    loading,
    status,
    error,
    isAuthenticated: Boolean(user),
    isAdmin: user?.role === 'admin',
    login,
    register,
    logout,
    refresh,
  }
}
