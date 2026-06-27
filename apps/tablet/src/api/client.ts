const DEFAULT_BASE_URL = process.env['API_BASE_URL'] ?? 'http://localhost:8000'

export interface ApiClient {
  get<T>(path: string): Promise<T>
  post<T>(path: string, body: unknown): Promise<T>
}

export function makeApiClient(baseUrl: string, getToken: () => string | null): ApiClient {
  async function request<T>(path: string, init: RequestInit): Promise<T> {
    const token = getToken()
    const headers: HeadersInit = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch(`${baseUrl}${path}`, { ...init, headers })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`API ${init.method ?? 'GET'} ${path} → ${res.status}: ${text}`)
    }
    return res.json() as Promise<T>
  }

  return {
    get: <T>(path: string) => request<T>(path, { method: 'GET' }),
    post: <T>(path: string, body: unknown) =>
      request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  }
}

// Module-level singleton configured after login
let _client: ApiClient | null = null

export function initApiClient(getToken: () => string | null, baseUrl = DEFAULT_BASE_URL): void {
  _client = makeApiClient(baseUrl, getToken)
}

export function getApiClient(): ApiClient {
  if (!_client) throw new Error('API client not initialised — call initApiClient() first')
  return _client
}
