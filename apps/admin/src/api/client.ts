import axios from 'axios'

export const BASE_URL = (import.meta as Record<string, Record<string, string>>).env?.VITE_API_URL ?? 'http://localhost:8000'

export const apiClient = axios.create({ baseURL: BASE_URL })

apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('ww_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  r => r,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('ww_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)
