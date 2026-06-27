import { useQuery } from '@tanstack/react-query'
import type { DashboardFilters } from '../api/dashboard'
import { getDashboard } from '../api/dashboard'

export function useDashboard(filters: DashboardFilters) {
  return useQuery({
    queryKey: ['dashboard', filters],
    queryFn: () => getDashboard(filters),
    staleTime: 30_000,
  })
}
