import type { Order } from '@wise-wash/shared'
import { apiClient } from './client'

export async function listOrders(branchId: string): Promise<Order[]> {
  const { data } = await apiClient.get<Order[]>(`/branches/${branchId}/orders`)
  return data
}

export async function getOrder(orderId: string): Promise<Order> {
  const { data } = await apiClient.get<Order>(`/orders/${orderId}`)
  return data
}
