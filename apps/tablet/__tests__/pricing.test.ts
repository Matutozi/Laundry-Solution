import {
  applyTurnaroundMultiplier,
  computeOrderTotal,
  lookupPrice,
} from '../src/services/pricing'

const RULES = [
  { serviceId: 'wash', tier: 1, priceKobo: 100_000 },
  { serviceId: 'wash', tier: 2, priceKobo: 80_000 },
  { serviceId: 'iron', tier: 1, priceKobo: 50_000 },
]

describe('applyTurnaroundMultiplier', () => {
  it('regular → 1× (unchanged)', () => {
    expect(applyTurnaroundMultiplier(100_000, 'regular')).toBe(100_000)
  })

  it('express → 1.5× in integer kobo (no float stored)', () => {
    // 100,000 × 3/2 = 150,000
    expect(applyTurnaroundMultiplier(100_000, 'express')).toBe(150_000)
  })

  it('same_day → 3×', () => {
    expect(applyTurnaroundMultiplier(100_000, 'same_day')).toBe(300_000)
  })

  it('truncates fractional kobo — never rounds up', () => {
    // 100,001 × 3/2 = 150,001.5 → 150,001
    expect(applyTurnaroundMultiplier(100_001, 'express')).toBe(150_001)
  })

  it('zero kobo stays zero', () => {
    expect(applyTurnaroundMultiplier(0, 'express')).toBe(0)
  })
})

describe('lookupPrice', () => {
  it('finds exact tier match', () => {
    expect(lookupPrice('wash', 2, RULES)).toBe(80_000)
  })

  it('falls back to tier 1 when tier missing', () => {
    expect(lookupPrice('iron', 2, RULES)).toBe(50_000)
  })

  it('returns 0 when service unknown', () => {
    expect(lookupPrice('dry_clean', 1, RULES)).toBe(0)
  })
})

describe('computeOrderTotal', () => {
  it('computes total for single line', () => {
    const { lines, totalKobo } = computeOrderTotal(
      [{ serviceId: 'wash', pieceCount: 2 }],
      1,
      'regular',
      RULES,
    )
    expect(lines).toHaveLength(1)
    expect(lines[0].unitPriceKobo).toBe(100_000)
    expect(lines[0].lineTotalKobo).toBe(200_000)
    expect(totalKobo).toBe(200_000)
  })

  it('sums multiple lines', () => {
    const { totalKobo } = computeOrderTotal(
      [
        { serviceId: 'wash', pieceCount: 2 },  // 200,000
        { serviceId: 'iron', pieceCount: 1 },  // 50,000
      ],
      1,
      'regular',
      RULES,
    )
    expect(totalKobo).toBe(250_000)
  })

  it('applies turnaround multiplier to every line', () => {
    const { lines, totalKobo } = computeOrderTotal(
      [
        { serviceId: 'wash', pieceCount: 1 },  // 100,000 × 1.5 = 150,000
        { serviceId: 'iron', pieceCount: 1 },  //  50,000 × 1.5 =  75,000
      ],
      1,
      'express',
      RULES,
    )
    expect(lines[0].unitPriceKobo).toBe(150_000)
    expect(lines[1].unitPriceKobo).toBe(75_000)
    expect(totalKobo).toBe(225_000)
  })

  it('uses tier-specific rule when available', () => {
    const { totalKobo } = computeOrderTotal(
      [{ serviceId: 'wash', pieceCount: 1 }],
      2,        // tier 2 rule: 80,000
      'regular',
      RULES,
    )
    expect(totalKobo).toBe(80_000)
  })

  it('never produces a float total', () => {
    const { totalKobo } = computeOrderTotal(
      [{ serviceId: 'wash', pieceCount: 3 }],
      1,
      'express',  // 100,000 × 3/2 = 150,000 per unit
      RULES,
    )
    expect(Number.isInteger(totalKobo)).toBe(true)
    expect(totalKobo).toBe(450_000)
  })

  it('returns 0 for empty lines', () => {
    const { totalKobo } = computeOrderTotal([], 1, 'regular', RULES)
    expect(totalKobo).toBe(0)
  })
})
