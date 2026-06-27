import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithQuery } from '../../test/utils'
import { server } from '../../test/server'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { PricingEditor } from './PricingEditor'
import type { PricingMatrix } from '@wise-wash/shared'

const BASE = 'http://localhost:8000'

const matrix: PricingMatrix = {
  services: [
    { id: 'svc-wash', name: 'Washing' },
    { id: 'svc-iron', name: 'Ironing' },
  ],
  rules: [
    { service_id: 'svc-wash', tier: 1, price_kobo: 100_000 },
    { service_id: 'svc-wash', tier: 2, price_kobo: 150_000 },
    { service_id: 'svc-wash', tier: 3, price_kobo: 200_000 },
    { service_id: 'svc-iron', tier: 1, price_kobo: 50_000 },
    { service_id: 'svc-iron', tier: 2, price_kobo: 75_000 },
    { service_id: 'svc-iron', tier: 3, price_kobo: 100_000 },
  ],
}

describe('PricingEditor', () => {
  it('renders the table with tier column headers', () => {
    renderWithQuery(<PricingEditor matrix={matrix} />)
    expect(screen.getByText('Tier 1')).toBeInTheDocument()
    expect(screen.getByText('Tier 2')).toBeInTheDocument()
    expect(screen.getByText('Tier 3')).toBeInTheDocument()
  })

  it('renders a row for each service', () => {
    renderWithQuery(<PricingEditor matrix={matrix} />)
    expect(screen.getByText('Washing')).toBeInTheDocument()
    expect(screen.getByText('Ironing')).toBeInTheDocument()
  })

  it('shows existing prices converted from kobo to naira', () => {
    renderWithQuery(<PricingEditor matrix={matrix} />)
    // 100,000 kobo = ₦1000
    const input = screen.getByLabelText('Washing tier 1 price')
    expect(input).toHaveValue(1000)
  })

  it('updates input value when user types', async () => {
    renderWithQuery(<PricingEditor matrix={matrix} />)
    const input = screen.getByLabelText('Washing tier 1 price')
    fireEvent.change(input, { target: { value: '1200' } })
    expect(input).toHaveValue(1200)
  })

  it('calls PUT endpoint with kobo value on blur', async () => {
    const captured: { serviceId: string; tier: number; price_kobo: number }[] = []

    server.use(
      http.put(`${BASE}/admin/pricing/:serviceId/rules/:tier`, async ({ request, params }) => {
        const body = await request.json() as { price_kobo: number }
        captured.push({ serviceId: String(params.serviceId), tier: Number(params.tier), price_kobo: body.price_kobo })
        return HttpResponse.json({ service_id: params.serviceId, tier: Number(params.tier), price_kobo: body.price_kobo })
      }),
    )

    renderWithQuery(<PricingEditor matrix={matrix} />)
    const input = screen.getByLabelText('Washing tier 1 price')

    fireEvent.change(input, { target: { value: '1500' } })
    fireEvent.blur(input)

    await waitFor(() => expect(captured.length).toBe(1))
    expect(captured[0].serviceId).toBe('svc-wash')
    expect(captured[0].tier).toBe(1)
    // 1500 naira × 100 = 150,000 kobo — integer, no floats
    expect(captured[0].price_kobo).toBe(150_000)
  })

  it('does not call PUT when value is unchanged', async () => {
    const calls: number[] = []
    server.use(
      http.put(`${BASE}/admin/pricing/:serviceId/rules/:tier`, () => {
        calls.push(1)
        return HttpResponse.json({})
      }),
    )

    renderWithQuery(<PricingEditor matrix={matrix} />)
    const input = screen.getByLabelText('Washing tier 1 price')
    // blur without changing value
    fireEvent.blur(input)

    // small delay — should still be 0
    await new Promise(r => setTimeout(r, 50))
    expect(calls.length).toBe(0)
  })

  it('shows validation error for non-numeric input', async () => {
    renderWithQuery(<PricingEditor matrix={matrix} />)
    const input = screen.getByLabelText('Ironing tier 2 price')
    fireEvent.change(input, { target: { value: 'abc' } })
    fireEvent.blur(input)
    await waitFor(() => expect(screen.getByText(/Enter a whole number/)).toBeInTheDocument())
  })

  it('renders inputs for all service × tier combinations', () => {
    renderWithQuery(<PricingEditor matrix={matrix} />)
    // 2 services × 3 tiers = 6 inputs
    const inputs = screen.getAllByRole('spinbutton')
    expect(inputs).toHaveLength(6)
  })

  it('renders ₦ currency symbol for each input', () => {
    renderWithQuery(<PricingEditor matrix={matrix} />)
    const symbols = screen.getAllByText('₦')
    expect(symbols.length).toBeGreaterThanOrEqual(6)
  })
})
