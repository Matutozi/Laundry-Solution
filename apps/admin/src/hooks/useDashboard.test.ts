import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { createElement } from 'react'
import { describe, expect, it } from 'vitest'
import { server } from '../test/server'
import { useDashboard } from './useDashboard'

const BASE = 'http://localhost:8000'

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client: qc }, children)
}

describe('useDashboard', () => {
  it('returns metrics from API', async () => {
    server.use(
      http.get(`${BASE}/admin/dashboard`, () =>
        HttpResponse.json({ revenue_kobo: 500_000, order_count: 5, outstanding_kobo: 100_000 }),
      ),
    )

    const { result } = renderHook(() => useDashboard({}), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.revenue_kobo).toBe(500_000)
    expect(result.current.data?.order_count).toBe(5)
    expect(result.current.data?.outstanding_kobo).toBe(100_000)
  })

  it('starts in loading state', () => {
    const { result } = renderHook(() => useDashboard({}), { wrapper })
    expect(result.current.isLoading).toBe(true)
  })

  it('passes branch_id filter as query param', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/admin/dashboard`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ revenue_kobo: 0, order_count: 0, outstanding_kobo: 0 })
      }),
    )

    const { result } = renderHook(() => useDashboard({ branchId: 'branch-abc' }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(capturedUrl).toContain('branch_id=branch-abc')
  })

  it('passes from_date filter as query param', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/admin/dashboard`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ revenue_kobo: 0, order_count: 0, outstanding_kobo: 0 })
      }),
    )

    const { result } = renderHook(() => useDashboard({ fromDate: '2026-01-01' }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(capturedUrl).toContain('from_date=2026-01-01')
  })

  it('passes to_date filter as query param', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/admin/dashboard`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ revenue_kobo: 0, order_count: 0, outstanding_kobo: 0 })
      }),
    )

    const { result } = renderHook(() => useDashboard({ toDate: '2026-06-30' }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(capturedUrl).toContain('to_date=2026-06-30')
  })

  it('returns isError on API failure', async () => {
    server.use(
      http.get(`${BASE}/admin/dashboard`, () => HttpResponse.json({ detail: 'Forbidden' }, { status: 403 })),
    )

    const { result } = renderHook(() => useDashboard({}), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it('does not duplicate outstanding with revenue', async () => {
    server.use(
      http.get(`${BASE}/admin/dashboard`, () =>
        HttpResponse.json({ revenue_kobo: 300_000, order_count: 3, outstanding_kobo: 200_000 }),
      ),
    )

    const { result } = renderHook(() => useDashboard({}), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // revenue + outstanding = total billed = 500,000
    const { revenue_kobo, outstanding_kobo } = result.current.data!
    expect(revenue_kobo + outstanding_kobo).toBe(500_000)
  })
})
