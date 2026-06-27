import type { Customer } from '@wise-wash/shared'
import { apiClient } from './client'

export async function searchCustomers(q: string): Promise<Customer[]> {
  const { data } = await apiClient.get<Customer[]>('/customers', { params: { q } })
  return data
}

export async function createCustomer(payload: Omit<Customer, 'id'>): Promise<Customer> {
  const { data } = await apiClient.post<Customer>('/customers', payload)
  return data
}
