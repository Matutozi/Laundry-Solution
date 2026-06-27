import type { PriceRule, PricingMatrix, Service } from '@wise-wash/shared'
import { useState } from 'react'
import { useUpdatePriceRule } from '../../hooks/usePricing'

const TIERS = [1, 2, 3] as const

interface Props {
  matrix: PricingMatrix
}

function ruleMap(rules: PriceRule[]): Map<string, number> {
  const m = new Map<string, number>()
  for (const r of rules) m.set(`${r.service_id}:${r.tier}`, r.price_kobo)
  return m
}

export function PricingEditor({ matrix }: Props) {
  const { services, rules } = matrix
  // Local edits: key "serviceId:tier" → naira (integer)
  const [edits, setEdits] = useState<Map<string, string>>(() => {
    const m = new Map<string, string>()
    for (const r of rules) m.set(`${r.service_id}:${r.tier}`, String(Math.trunc(r.price_kobo / 100)))
    return m
  })
  const [saving, setSaving] = useState<string | null>(null)
  const [errors, setErrors] = useState<Map<string, string>>(new Map())
  const { mutateAsync } = useUpdatePriceRule()

  const current = ruleMap(rules)

  function cellKey(svc: Service, tier: number) {
    return `${svc.id}:${tier}`
  }

  function getValue(svc: Service, tier: number): string {
    const key = cellKey(svc, tier)
    if (edits.has(key)) return edits.get(key)!
    const kobo = current.get(key)
    return kobo !== undefined ? String(Math.trunc(kobo / 100)) : ''
  }

  function handleChange(svc: Service, tier: number, value: string) {
    const key = cellKey(svc, tier)
    setEdits(prev => new Map(prev).set(key, value))
    setErrors(prev => { const n = new Map(prev); n.delete(key); return n })
  }

  async function handleBlur(svc: Service, tier: number) {
    const key = cellKey(svc, tier)
    const raw = edits.get(key)
    if (raw === undefined) return

    const naira = parseInt(raw, 10)
    if (isNaN(naira) || naira < 0) {
      setErrors(prev => new Map(prev).set(key, 'Enter a whole number ≥ 0'))
      return
    }
    const priceKobo = naira * 100  // integer multiplication — no floats
    const existing = current.get(key)
    if (existing === priceKobo) return  // no change

    setSaving(key)
    try {
      await mutateAsync({ serviceId: svc.id, tier, priceKobo })
    } catch {
      setErrors(prev => new Map(prev).set(key, 'Save failed'))
    } finally {
      setSaving(null)
    }
  }

  return (
    <div>
      <table style={{ borderCollapse: 'collapse' }} aria-label="Pricing matrix">
        <thead>
          <tr>
            <th style={{ padding: '8px 16px', textAlign: 'left' }}>Service</th>
            {TIERS.map(t => (
              <th key={t} style={{ padding: '8px 16px' }}>Tier {t}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {services.map(svc => (
            <tr key={svc.id}>
              <td style={{ padding: '8px 16px', fontWeight: 600 }}>{svc.name}</td>
              {TIERS.map(tier => {
                const key = cellKey(svc, tier)
                const err = errors.get(key)
                return (
                  <td key={tier} style={{ padding: '4px 8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span>₦</span>
                      <input
                        aria-label={`${svc.name} tier ${tier} price`}
                        type="number"
                        min={0}
                        step={1}
                        value={getValue(svc, tier)}
                        onChange={e => handleChange(svc, tier, e.target.value)}
                        onBlur={() => handleBlur(svc, tier)}
                        style={{ width: 100, borderColor: err ? 'red' : undefined }}
                        disabled={saving === key}
                      />
                      {saving === key && <span aria-label="Saving…">…</span>}
                    </div>
                    {err && <div style={{ color: 'red', fontSize: 12 }}>{err}</div>}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
