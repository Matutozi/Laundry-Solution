import { PricingEditor } from '../components/PricingEditor/PricingEditor'
import { usePricing } from '../hooks/usePricing'

export function PricingPage() {
  const { data, isLoading, isError } = usePricing()

  return (
    <div style={{ padding: 24 }}>
      <h1>Pricing Matrix</h1>
      <p style={{ color: '#666', marginBottom: 16 }}>
        Prices are entered in Naira (₦). Changes are saved automatically on blur.
      </p>
      {isLoading && <p>Loading pricing…</p>}
      {isError && <p style={{ color: 'red' }}>Failed to load pricing data</p>}
      {data && <PricingEditor matrix={data} />}
    </div>
  )
}
