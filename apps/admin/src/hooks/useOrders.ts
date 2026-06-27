import { useQuery } from '@tanstack/react-query'
import { listOrders } from '../api/orders'

export function useOrders(branchId: string) {
  return useQuery({
    queryKey: ['orders', branchId],
    queryFn: () => listOrders(branchId),
    enabled: Boolean(branchId),
  })
}
