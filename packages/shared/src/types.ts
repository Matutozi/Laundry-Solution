// Shared domain types — mirrored from the FastAPI backend models.
// All monetary values are integer kobo (100 kobo = ₦1). Never floats.

export type OrderStatus =
  | 'received'
  | 'processing'
  | 'ready'
  | 'picked_up'
  | 'delivered'
  | 'cancelled'

export type Turnaround = 'regular' | 'express' | 'same_day'
export type PaymentMethod = 'cash' | 'transfer' | 'pos'

export interface Customer {
  id: string
  name: string
  phone: string
  tier: number
}

export interface Service {
  id: string
  name: string
}

export interface PriceRule {
  service_id: string
  tier: number
  price_kobo: number
}

export interface PricingMatrix {
  services: Service[]
  rules: PriceRule[]
}

export interface OrderLine {
  id: string
  service_id: string
  piece_count: number
  unit_price_kobo: number
  line_total_kobo: number
}

export interface Order {
  id: string
  branch_id: string
  customer_id: string
  attendant_id: string
  status: OrderStatus
  turnaround: Turnaround
  pickup_code: string
  total_kobo: number
  version: number
  lines?: OrderLine[]
}

export interface Payment {
  id: string
  order_id: string
  amount_kobo: number
  method: PaymentMethod
  recorded_at: string
  outstanding_kobo: number
}

export interface DashboardMetrics {
  revenue_kobo: number
  order_count: number
  outstanding_kobo: number
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface Branch {
  id: string
  name: string
  organization_id: string
}

/** Convert integer kobo to a ₦ display string. No floats stored — display only. */
export function formatNaira(kobo: number): string {
  const naira = Math.trunc(kobo / 100)
  const koboRemainder = Math.abs(kobo % 100)
  const sign = kobo < 0 ? '-' : ''
  const nairaAbs = Math.abs(naira)
  return `${sign}₦${nairaAbs.toLocaleString('en-NG')}.${koboRemainder.toString().padStart(2, '0')}`
}
