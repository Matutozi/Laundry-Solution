/**
 * Local pricing — mirrors the server's price_order() logic.
 * All values are integer kobo. No floats ever stored or computed.
 */

export type Turnaround = 'regular' | 'express' | 'same_day'

export interface LineInput {
  serviceId: string
  pieceCount: number
}

export interface PricedLine {
  serviceId: string
  pieceCount: number
  unitPriceKobo: number
  lineTotalKobo: number
}

export interface PricingResult {
  lines: PricedLine[]
  totalKobo: number
}

// Multipliers stored as [numerator, denominator] to stay in integer kobo
const TURNAROUND_MULTIPLIER: Record<Turnaround, [number, number]> = {
  regular:  [1, 1],
  express:  [3, 2],   // 1.5×
  same_day: [3, 1],   // 3×
}

export function applyTurnaroundMultiplier(kobo: number, turnaround: Turnaround): number {
  const [n, d] = TURNAROUND_MULTIPLIER[turnaround]
  // Integer math: multiply first, then divide and truncate
  return Math.trunc((kobo * n) / d)
}

/**
 * Look up the price (kobo) for a service at a given customer tier.
 * Falls back to tier 1 if the exact tier has no rule.
 */
export function lookupPrice(
  serviceId: string,
  tier: number,
  rules: Array<{ serviceId: string; tier: number; priceKobo: number }>,
): number {
  const exact = rules.find(r => r.serviceId === serviceId && r.tier === tier)
  if (exact) return exact.priceKobo
  const fallback = rules.find(r => r.serviceId === serviceId && r.tier === 1)
  return fallback?.priceKobo ?? 0
}

export function computeOrderTotal(
  lines: LineInput[],
  tier: number,
  turnaround: Turnaround,
  rules: Array<{ serviceId: string; tier: number; priceKobo: number }>,
): PricingResult {
  const pricedLines: PricedLine[] = lines.map(l => {
    const baseUnit = lookupPrice(l.serviceId, tier, rules)
    const unitPriceKobo = applyTurnaroundMultiplier(baseUnit, turnaround)
    return {
      serviceId: l.serviceId,
      pieceCount: l.pieceCount,
      unitPriceKobo,
      lineTotalKobo: unitPriceKobo * l.pieceCount,
    }
  })
  const totalKobo = pricedLines.reduce((sum, l) => sum + l.lineTotalKobo, 0)
  return { lines: pricedLines, totalKobo }
}
