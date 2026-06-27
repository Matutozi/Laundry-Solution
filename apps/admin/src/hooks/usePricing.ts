import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getPricing, updatePriceRule } from '../api/pricing'

export function usePricing() {
  return useQuery({
    queryKey: ['pricing'],
    queryFn: getPricing,
    staleTime: 60_000,
  })
}

export function useUpdatePriceRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ serviceId, tier, priceKobo }: { serviceId: string; tier: number; priceKobo: number }) =>
      updatePriceRule(serviceId, tier, priceKobo),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pricing'] }),
  })
}
