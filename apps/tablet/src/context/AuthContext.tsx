import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { initApiClient } from '../api/client'

const API_BASE = process.env['API_BASE_URL'] ?? 'http://localhost:8000'

interface AuthState {
  token: string | null
  branchId: string | null
  attendantId: string | null
  deviceId: string
}

interface AuthContextValue extends AuthState {
  login(token: string, branchId: string, attendantId: string): void
  logout(): void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function makeDeviceId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    branchId: null,
    attendantId: null,
    deviceId: makeDeviceId(),
  })

  useEffect(() => {
    initApiClient(() => state.token, API_BASE)
  }, [state.token])

  const login = useCallback(
    (token: string, branchId: string, attendantId: string) => {
      setState(s => ({ ...s, token, branchId, attendantId }))
    },
    [],
  )

  const logout = useCallback(() => {
    setState(s => ({ ...s, token: null, branchId: null, attendantId: null }))
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
