import { HttpResponse, http } from 'msw'

const BASE = 'http://localhost:8000'

export const defaultHandlers = [
  http.get(`${BASE}/admin/dashboard`, () =>
    HttpResponse.json({ revenue_kobo: 0, order_count: 0, outstanding_kobo: 0 }),
  ),
  http.get(`${BASE}/admin/pricing`, () =>
    HttpResponse.json({
      services: [
        { id: 'svc-wash', name: 'Washing' },
        { id: 'svc-iron', name: 'Ironing' },
      ],
      rules: [
        { service_id: 'svc-wash', tier: 1, price_kobo: 100_000 },
        { service_id: 'svc-wash', tier: 2, price_kobo: 150_000 },
        { service_id: 'svc-iron', name: 'Ironing', tier: 1, price_kobo: 50_000 },
      ],
    }),
  ),
  http.put(`${BASE}/admin/pricing/:serviceId/rules/:tier`, async ({ request, params }) => {
    const body = await request.json() as { price_kobo: number }
    return HttpResponse.json({
      service_id: params.serviceId,
      tier: Number(params.tier),
      price_kobo: body.price_kobo,
    })
  }),
  http.get(`${BASE}/customers`, () => HttpResponse.json([])),
  http.get(`${BASE}/branches/:branchId/orders`, () => HttpResponse.json([])),
]
