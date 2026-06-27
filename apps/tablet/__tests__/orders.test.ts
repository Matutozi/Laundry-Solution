import { makeDb } from './helpers/makeDb'
import { OrderModel } from '../src/db/models/OrderModel'
import { OrderLineModel } from '../src/db/models/OrderLineModel'
import { CustomerModel } from '../src/db/models/CustomerModel'
import { PriceRuleModel } from '../src/db/models/PriceRuleModel'
import { ServiceModel } from '../src/db/models/ServiceModel'
import {
  generateOfflinePickupCode,
  createOrderLocally,
  createCustomerLocally,
  updateOrderStatusLocally,
} from '../src/services/orders'
import { recordPaymentLocally, getTotalPaidKobo } from '../src/services/payments'
import { Q } from '@nozbe/watermelondb'

// ── helpers ───────────────────────────────────────────────────────────────────

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

const BRANCH_ID = '11111111-0000-0000-0000-000000000001'
const DEVICE_ID = '22222222-0000-0000-0000-000000000002'
const ATTENDANT_ID = '33333333-0000-0000-0000-000000000003'

const RULES = [
  { serviceId: 'svc-wash', tier: 1, priceKobo: 100_000 },
  { serviceId: 'svc-iron', tier: 1, priceKobo: 50_000 },
]

async function seedPriceRules(db: ReturnType<typeof makeDb>) {
  await db.write(async () => {
    for (const r of RULES) {
      await db.get<PriceRuleModel>('price_rules').create(rule => {
        rule._raw.id = `${r.serviceId}:${r.tier}`
        rule.serviceId = r.serviceId
        rule.tier = r.tier
        rule.priceKobo = r.priceKobo
      })
    }
    await db.get<ServiceModel>('services').create(s => {
      s._raw.id = 'svc-wash'
      s.name = 'Wash & Fold'
    })
    await db.get<ServiceModel>('services').create(s => {
      s._raw.id = 'svc-iron'
      s.name = 'Ironing'
    })
  })
}

// ── generateOfflinePickupCode ─────────────────────────────────────────────────

describe('generateOfflinePickupCode', () => {
  it('is 11 characters long', () => {
    const code = generateOfflinePickupCode(BRANCH_ID, DEVICE_ID)
    expect(code).toHaveLength(11)
  })

  it('starts with branch prefix (first 3 hex chars of branch UUID, uppercased)', () => {
    const code = generateOfflinePickupCode(BRANCH_ID, DEVICE_ID)
    // branch: 11111111-0000-... → stripped: 111111110000... → first 3 → '111'
    expect(code.slice(0, 3)).toBe('111')
  })

  it('contains device prefix in positions 3-5', () => {
    const code = generateOfflinePickupCode(BRANCH_ID, DEVICE_ID)
    // device: 22222222-0000-... → '222'
    expect(code.slice(3, 6)).toBe('222')
  })

  it('generates different codes on successive calls (random suffix)', () => {
    const codes = new Set(
      Array.from({ length: 20 }, () => generateOfflinePickupCode(BRANCH_ID, DEVICE_ID)),
    )
    // With 5 random chars from 36-char alphabet, collision probability is negligible
    expect(codes.size).toBeGreaterThan(1)
  })

  it('only contains uppercase alphanumeric characters', () => {
    for (let i = 0; i < 20; i++) {
      const code = generateOfflinePickupCode(BRANCH_ID, DEVICE_ID)
      expect(code).toMatch(/^[A-Z0-9]+$/)
    }
  })
})

// ── createOrderLocally ────────────────────────────────────────────────────────

describe('createOrderLocally', () => {
  it('creates an order record with status=received and is_synced=false', async () => {
    const db = makeDb()
    const order = await createOrderLocally(db, {
      id: uuid(),
      branchId: BRANCH_ID,
      attendantId: ATTENDANT_ID,
      customerId: uuid(),
      turnaround: 'regular',
      lines: [{ serviceId: 'svc-wash', pieceCount: 2 }],
      deviceId: DEVICE_ID,
      customerTier: 1,
      rules: RULES,
    })

    expect(order.status).toBe('received')
    expect(order.isSynced).toBe(false)
    expect(order.serverSeq).toBeNull()
    expect(order.version).toBe(1)
  })

  it('computes total_kobo from rules (2 × wash @ 100,000 = 200,000)', async () => {
    const db = makeDb()
    const order = await createOrderLocally(db, {
      id: uuid(),
      branchId: BRANCH_ID,
      attendantId: ATTENDANT_ID,
      customerId: uuid(),
      turnaround: 'regular',
      lines: [{ serviceId: 'svc-wash', pieceCount: 2 }],
      deviceId: DEVICE_ID,
      customerTier: 1,
      rules: RULES,
    })

    expect(order.totalKobo).toBe(200_000)
  })

  it('creates corresponding order_line records', async () => {
    const db = makeDb()
    const id = uuid()
    await createOrderLocally(db, {
      id,
      branchId: BRANCH_ID,
      attendantId: ATTENDANT_ID,
      customerId: uuid(),
      turnaround: 'regular',
      lines: [
        { serviceId: 'svc-wash', pieceCount: 2 },
        { serviceId: 'svc-iron', pieceCount: 1 },
      ],
      deviceId: DEVICE_ID,
      customerTier: 1,
      rules: RULES,
    })

    const lines = await db
      .get<OrderLineModel>('order_lines')
      .query(Q.where('order_id', id))
      .fetch()

    expect(lines).toHaveLength(2)
    expect(lines.find(l => l.serviceId === 'svc-wash')?.pieceCount).toBe(2)
    expect(lines.find(l => l.serviceId === 'svc-iron')?.pieceCount).toBe(1)
  })

  it('applies express multiplier: 100,000 × 1.5 = 150,000 per wash unit', async () => {
    const db = makeDb()
    const id = uuid()
    const order = await createOrderLocally(db, {
      id,
      branchId: BRANCH_ID,
      attendantId: ATTENDANT_ID,
      customerId: uuid(),
      turnaround: 'express',
      lines: [{ serviceId: 'svc-wash', pieceCount: 1 }],
      deviceId: DEVICE_ID,
      customerTier: 1,
      rules: RULES,
    })

    expect(order.totalKobo).toBe(150_000)
    const lines = await db
      .get<OrderLineModel>('order_lines')
      .query(Q.where('order_id', id))
      .fetch()
    expect(lines[0].unitPriceKobo).toBe(150_000)
  })

  it('total_kobo is always an integer — no floats', async () => {
    const db = makeDb()
    const order = await createOrderLocally(db, {
      id: uuid(),
      branchId: BRANCH_ID,
      attendantId: ATTENDANT_ID,
      customerId: uuid(),
      turnaround: 'express',
      lines: [{ serviceId: 'svc-wash', pieceCount: 3 }],
      deviceId: DEVICE_ID,
      customerTier: 1,
      rules: RULES,
    })
    expect(Number.isInteger(order.totalKobo)).toBe(true)
  })

  it('generates an 11-char pickup code', async () => {
    const db = makeDb()
    const order = await createOrderLocally(db, {
      id: uuid(),
      branchId: BRANCH_ID,
      attendantId: ATTENDANT_ID,
      customerId: uuid(),
      turnaround: 'regular',
      lines: [{ serviceId: 'svc-wash', pieceCount: 1 }],
      deviceId: DEVICE_ID,
      customerTier: 1,
      rules: RULES,
    })
    expect(order.pickupCode).toHaveLength(11)
    expect(order.pickupCode).toMatch(/^[A-Z0-9]+$/)
  })
})

// ── createCustomerLocally ─────────────────────────────────────────────────────

describe('createCustomerLocally', () => {
  it('stores customer with isDirty=true and no serverSeq', async () => {
    const db = makeDb()
    const customer = await createCustomerLocally(db, uuid(), 'Adaeze Obi', '08012345678')
    expect(customer.isDirty).toBe(true)
    expect(customer.serverSeq).toBeNull()
    expect(customer.name).toBe('Adaeze Obi')
    expect(customer.phone).toBe('08012345678')
    expect(customer.tier).toBe(1)
  })
})

// ── updateOrderStatusLocally ──────────────────────────────────────────────────

describe('updateOrderStatusLocally', () => {
  it('updates status and bumps version, marks is_synced=false', async () => {
    const db = makeDb()
    const order = await createOrderLocally(db, {
      id: uuid(),
      branchId: BRANCH_ID,
      attendantId: ATTENDANT_ID,
      customerId: uuid(),
      turnaround: 'regular',
      lines: [{ serviceId: 'svc-wash', pieceCount: 1 }],
      deviceId: DEVICE_ID,
      customerTier: 1,
      rules: RULES,
    })

    await updateOrderStatusLocally(db, order, 'processing')
    const updated = await db.get<OrderModel>('orders').find(order.id)
    expect(updated.status).toBe('processing')
    expect(updated.version).toBe(2)
    expect(updated.isSynced).toBe(false)
  })
})

// ── recordPaymentLocally + getTotalPaidKobo ───────────────────────────────────

describe('payments', () => {
  it('records a payment and calculates outstanding correctly', async () => {
    const db = makeDb()
    const orderId = uuid()

    // Create a minimal order record directly for this test
    await db.write(async () => {
      await db.get<OrderModel>('orders').create(o => {
        o._raw.id = orderId
        o.branchId = BRANCH_ID
        o.attendantId = ATTENDANT_ID
        o.customerId = uuid()
        o.status = 'received'
        o.turnaround = 'regular'
        o.pickupCode = 'TESTCODE111'
        o.totalKobo = 250_000
        o.version = 1
        o.serverSeq = null
        o.isSynced = false
        o.createdAtDevice = Date.now()
      })
    })

    await recordPaymentLocally(db, uuid(), orderId, 100_000, 'cash')
    expect(await getTotalPaidKobo(db, orderId)).toBe(100_000)

    await recordPaymentLocally(db, uuid(), orderId, 50_000, 'pos')
    expect(await getTotalPaidKobo(db, orderId)).toBe(150_000)
  })

  it('stores payment with is_synced=false', async () => {
    const db = makeDb()
    const orderId = uuid()
    await db.write(async () => {
      await db.get<OrderModel>('orders').create(o => {
        o._raw.id = orderId
        o.branchId = BRANCH_ID
        o.attendantId = ATTENDANT_ID
        o.customerId = uuid()
        o.status = 'received'
        o.turnaround = 'regular'
        o.pickupCode = 'TESTCODE112'
        o.totalKobo = 100_000
        o.version = 1
        o.serverSeq = null
        o.isSynced = false
        o.createdAtDevice = Date.now()
      })
    })

    const payment = await recordPaymentLocally(db, uuid(), orderId, 50_000, 'transfer')
    expect(payment.isSynced).toBe(false)
    expect(payment.serverSeq).toBeNull()
  })
})
