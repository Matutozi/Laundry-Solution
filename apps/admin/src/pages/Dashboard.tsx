import { formatNaira } from '@wise-wash/shared'
import { useState } from 'react'
import { useDashboard } from '../hooks/useDashboard'

export function DashboardPage() {
  const [branchId, setBranchId] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')

  const filters = {
    branchId: branchId || undefined,
    fromDate: fromDate || undefined,
    toDate: toDate || undefined,
  }

  const { data, isLoading, isError } = useDashboard(filters)

  return (
    <div style={{ padding: 24 }}>
      <h1>Dashboard</h1>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <label>
          Branch ID
          <br />
          <input
            aria-label="Branch ID"
            value={branchId}
            onChange={e => setBranchId(e.target.value)}
            placeholder="all branches"
          />
        </label>
        <label>
          From
          <br />
          <input
            aria-label="From date"
            type="date"
            value={fromDate}
            onChange={e => setFromDate(e.target.value)}
          />
        </label>
        <label>
          To
          <br />
          <input
            aria-label="To date"
            type="date"
            value={toDate}
            onChange={e => setToDate(e.target.value)}
          />
        </label>
      </div>

      {/* Metrics */}
      {isLoading && <p>Loading…</p>}
      {isError && <p style={{ color: 'red' }}>Failed to load dashboard</p>}
      {data && (
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <MetricCard label="Revenue" value={formatNaira(data.revenue_kobo)} />
          <MetricCard label="Orders" value={data.order_count.toString()} />
          <MetricCard label="Outstanding" value={formatNaira(data.outstanding_kobo)} />
        </div>
      )}
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{ border: '1px solid #ccc', borderRadius: 8, padding: 20, minWidth: 160 }}
      aria-label={`${label}: ${value}`}
    >
      <div style={{ fontSize: 13, color: '#666' }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, marginTop: 4 }}>{value}</div>
    </div>
  )
}
