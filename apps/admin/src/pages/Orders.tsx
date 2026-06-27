import type { Order, OrderStatus } from '@wise-wash/shared'
import { formatNaira } from '@wise-wash/shared'
import { useState } from 'react'
import { useOrders } from '../hooks/useOrders'

const STATUS_BADGE: Record<OrderStatus, string> = {
  received: '#bbb',
  processing: '#f0a500',
  ready: '#2196f3',
  picked_up: '#4caf50',
  delivered: '#4caf50',
  cancelled: '#e53935',
}

export function OrdersPage() {
  const [branchId, setBranchId] = useState('')
  const [statusFilter, setStatusFilter] = useState<OrderStatus | ''>('')
  const { data: orders = [], isLoading } = useOrders(branchId)

  const visible = statusFilter ? orders.filter((o: Order) => o.status === statusFilter) : orders

  return (
    <div style={{ padding: 24 }}>
      <h1>Orders</h1>
      <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
        <input
          aria-label="Branch ID"
          value={branchId}
          onChange={e => setBranchId(e.target.value)}
          placeholder="Enter branch ID to load orders"
          style={{ width: 320 }}
        />
        <select
          aria-label="Status filter"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as OrderStatus | '')}
        >
          <option value="">All statuses</option>
          {['received', 'processing', 'ready', 'picked_up', 'delivered', 'cancelled'].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      {isLoading && <p>Loading orders…</p>}
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr>
            {['Pickup Code', 'Status', 'Total', 'Turnaround'].map(h => (
              <th key={h} style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: '6px 12px' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visible.map((o: Order) => (
            <tr key={o.id}>
              <td style={{ padding: '6px 12px', fontFamily: 'monospace' }}>{o.pickup_code}</td>
              <td style={{ padding: '6px 12px' }}>
                <span style={{ background: STATUS_BADGE[o.status], color: '#fff', borderRadius: 4, padding: '2px 8px', fontSize: 12 }}>
                  {o.status}
                </span>
              </td>
              <td style={{ padding: '6px 12px' }}>{formatNaira(o.total_kobo)}</td>
              <td style={{ padding: '6px 12px' }}>{o.turnaround}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!isLoading && branchId && visible.length === 0 && <p>No orders found.</p>}
    </div>
  )
}
