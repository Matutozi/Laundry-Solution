import type { TokenResponse } from '@wise-wash/shared'
import { apiClient } from './client'

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', { email, password })
  return data
}
