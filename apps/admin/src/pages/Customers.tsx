import type { Customer } from '@wise-wash/shared'
import { useEffect, useState } from 'react'
import { searchCustomers } from '../api/customers'

export function CustomersPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!query.trim()) { setResults([]); return }
    setLoading(true)
    const timer = setTimeout(async () => {
      try {
        setResults(await searchCustomers(query))
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  return (
    <div style={{ padding: 24 }}>
      <h1>Customers</h1>
      <input
        aria-label="Search customers"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search by name or phone…"
        style={{ width: 320 }}
      />
      {loading && <p>Searching…</p>}
      <table style={{ marginTop: 16, borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr>
            {['Name', 'Phone', 'Tier'].map(h => (
              <th key={h} style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: '6px 12px' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map(c => (
            <tr key={c.id}>
              <td style={{ padding: '6px 12px' }}>{c.name}</td>
              <td style={{ padding: '6px 12px' }}>{c.phone}</td>
              <td style={{ padding: '6px 12px' }}>{c.tier}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!loading && query && results.length === 0 && <p>No customers found.</p>}
    </div>
  )
}
