import type { PricingMatrix } from '@wise-wash/shared'
import { apiClient } from './client'

export async function getPricing(): Promise<PricingMatrix> {
  const { data } = await apiClient.get<PricingMatrix>('/admin/pricing')
  return data
}

export async function updatePriceRule(
  serviceId: string,
  tier: number,
  priceKobo: number,
): Promise<void> {
  await apiClient.put(`/admin/pricing/${serviceId}/rules/${tier}`, { price_kobo: priceKobo })
}
