import type { DashboardMetrics } from '@wise-wash/shared'
import { apiClient } from './client'

export interface DashboardFilters {
  branchId?: string
  fromDate?: string  // ISO date YYYY-MM-DD
  toDate?: string
}

export async function getDashboard(filters: DashboardFilters): Promise<DashboardMetrics> {
  const params: Record<string, string> = {}
  if (filters.branchId) params.branch_id = filters.branchId
  if (filters.fromDate) params.from_date = filters.fromDate
  if (filters.toDate) params.to_date = filters.toDate
  const { data } = await apiClient.get<DashboardMetrics>('/admin/dashboard', { params })
  return data
}
