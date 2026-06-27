import { Q } from '@nozbe/watermelondb'
import { makeDb } from './helpers/makeDb'
import { OrderModel } from '../src/db/models/OrderModel'
import { PaymentModel } from '../src/db/models/PaymentModel'
import { CustomerModel } from '../src/db/models/CustomerModel'
import { applyPull, getLastServerSeq } from '../src/sync/pull'
import { buildPushPayload } from '../src/sync/push'
import type { ApiClient } from '../src/api/client'

// ── fake API client ───────────────────────────────────────────────────────────

function fakeApi(
  pullResponse: object = { changes: { orders: [], payments: [], customers: [] }, server_seq: 0 },
  pushResponse: object = { reassigned_codes: {}, server_seq: 10 },
): ApiClient {
  return {
    get: jest.fn().mockResolvedValue(pullResponse),
    post: jest.fn().mockResolvedValue(pushResponse),
  }
}

const BRANCH_ID = 'aaaa0000-0000-0000-0000-000000000001'
const CUSTOMER_ID = 'cccc0000-0000-0000-0000-000000000001'

// ── applyPull ─────────────────────────────────────────────────────────────────

describe('applyPull', () => {
  it('inserts pulled orders into local DB', async () => {
    const db = makeDb()
    const api = fakeApi({
      changes: {
        orders: [
          {
            id: 'order-001',
            branch_id: BRANCH_ID,
            attendant_id: 'staff-001',
            customer_id: CUSTOMER_ID,
            status: 'received',
            turnaround: 'regular',
            pickup_code: 'ABC12345678',
            total_kobo: 200_000,
            version: 1,
            server_seq: 5,
          },
        ],
        payments: [],
        customers: [],
      },
      server_seq: 5,
    })

    await applyPull(db, api)

    const orders = await db.get<OrderModel>('orders').query().fetch()
    expect(orders).toHaveLength(1)
    expect(orders[0].id).toBe('order-001')
    expect(orders[0].totalKobo).toBe(200_000)
    expect(orders[0].isSynced).toBe(true)
  })

  it('inserts pulled customers', async () => {
    const db = makeDb()
    const api = fakeApi({
      changes: {
        orders: [],
        payments: [],
        customers: [
          { id: CUSTOMER_ID, name: 'Bola Tinubu', phone: '0801111', tier: 1, server_seq: 3 },
        ],
      },
      server_seq: 3,
    })

    await applyPull(db, api)

    const customers = await db.get<CustomerModel>('customers').query().fetch()
    expect(customers).toHaveLength(1)
    expect(customers[0].name).toBe('Bola Tinubu')
    expect(customers[0].isDirty).toBe(false)
  })

  it('inserts pulled payments', async () => {
    const db = makeDb()
    // seed order first so foreign key is satisfied conceptually
    await db.write(async () => {
      await db.get<OrderModel>('orders').create(o => {
        o._raw.id = 'order-001'
        o.branchId = BRANCH_ID
        o.attendantId = 'staff-001'
        o.customerId = CUSTOMER_ID
        o.status = 'received'
        o.turnaround = 'regular'
        o.pickupCode = 'ABC12345678'
        o.totalKobo = 200_000
        o.version = 1
        o.serverSeq = 5
        o.isSynced = true
        o.createdAtDevice = Date.now()
      })
    })

    const api = fakeApi({
      changes: {
        orders: [],
        payments: [
          {
            id: 'pay-001',
            order_id: 'order-001',
            amount_kobo: 100_000,
            method: 'cash',
            recorded_at: '2026-06-27T10:00:00Z',
            server_seq: 7,
          },
        ],
        customers: [],
      },
      server_seq: 7,
    })

    await applyPull(db, api)

    const payments = await db.get<PaymentModel>('payments').query().fetch()
    expect(payments).toHaveLength(1)
    expect(payments[0].amountKobo).toBe(100_000)
    expect(payments[0].isSynced).toBe(true)
  })

  it('updates an existing order from pull (status advances)', async () => {
    const db = makeDb()
    await db.write(async () => {
      await db.get<OrderModel>('orders').create(o => {
        o._raw.id = 'order-001'
        o.branchId = BRANCH_ID
        o.attendantId = 'staff-001'
        o.customerId = CUSTOMER_ID
        o.status = 'received'
        o.turnaround = 'regular'
        o.pickupCode = 'ABC12345678'
        o.totalKobo = 200_000
        o.version = 1
        o.serverSeq = 5
        o.isSynced = true
        o.createdAtDevice = Date.now()
      })
    })

    const api = fakeApi({
      changes: {
        orders: [{
          id: 'order-001',
          branch_id: BRANCH_ID,
          attendant_id: 'staff-001',
          customer_id: CUSTOMER_ID,
          status: 'ready',
          turnaround: 'regular',
          pickup_code: 'ABC12345678',
          total_kobo: 200_000,
          version: 2,
          server_seq: 12,
        }],
        payments: [],
        customers: [],
      },
      server_seq: 12,
    })

    await applyPull(db, api)

    const order = await db.get<OrderModel>('orders').find('order-001')
    expect(order.status).toBe('ready')
    expect(order.version).toBe(2)
    expect(order.serverSeq).toBe(12)
  })

  it('persists last_server_seq in the settings table', async () => {
    const db = makeDb()
    expect(await getLastServerSeq(db)).toBe(0)

    await applyPull(db, fakeApi({ changes: { orders: [], payments: [], customers: [] }, server_seq: 42 }))

    expect(await getLastServerSeq(db)).toBe(42)
  })

  it('passes since= to the pull endpoint', async () => {
    const db = makeDb()
    const api = fakeApi({ changes: { orders: [], payments: [], customers: [] }, server_seq: 7 })
    await applyPull(db, api)   // sets last_server_seq = 7
    await applyPull(db, api)   // second pull should use since=7
    expect((api.get as jest.Mock).mock.calls[1][0]).toContain('since=7')
  })

  it('is idempotent — replaying the same pull does not duplicate records', async () => {
    const db = makeDb()
    const payload = {
      changes: {
        orders: [{
          id: 'order-001',
          branch_id: BRANCH_ID,
          attendant_id: 'staff-001',
          customer_id: CUSTOMER_ID,
          status: 'received',
          turnaround: 'regular',
          pickup_code: 'ABC12345678',
          total_kobo: 200_000,
          version: 1,
          server_seq: 5,
        }],
        payments: [],
        customers: [],
      },
      server_seq: 5,
    }
    await applyPull(db, fakeApi(payload))
    await applyPull(db, fakeApi(payload))

    const orders = await db.get<OrderModel>('orders').query().fetch()
    expect(orders).toHaveLength(1)
  })
})

// ── buildPushPayload ──────────────────────────────────────────────────────────

describe('buildPushPayload', () => {
  const DEVICE_ID = 'device-abc'

  it('includes unsynced orders in created list', async () => {
    const db = makeDb()
    await db.write(async () => {
      await db.get<OrderModel>('orders').create(o => {
        o._raw.id = 'offline-order-1'
        o.branchId = BRANCH_ID
        o.attendantId = 'staff-001'
        o.customerId = CUSTOMER_ID
        o.status = 'received'
        o.turnaround = 'regular'
        o.pickupCode = '111222ABCDE'
        o.totalKobo = 150_000
        o.version = 1
        o.serverSeq = null      // no server seq → offline created
        o.isSynced = false
        o.createdAtDevice = Date.now()
      })
    })

    const payload = await buildPushPayload(db, DEVICE_ID)
    expect(payload.device_id).toBe(DEVICE_ID)
    expect(payload.changes.orders.created).toHaveLength(1)
    expect((payload.changes.orders.created[0] as any).id).toBe('offline-order-1')
    expect((payload.changes.orders.created[0] as any).pickup_code).toBe('111222ABCDE')
  })

  it('includes status-only updates for synced orders with local status change', async () => {
    const db = makeDb()
    await db.write(async () => {
      await db.get<OrderModel>('orders').create(o => {
        o._raw.id = 'server-order-1'
        o.branchId = BRANCH_ID
        o.attendantId = 'staff-001'
        o.customerId = CUSTOMER_ID
        o.status = 'processing'
        o.turnaround = 'regular'
        o.pickupCode = '333444FGHIJ'
        o.totalKobo = 200_000
        o.version = 2
        o.serverSeq = 5         // has server seq → came from server
        o.isSynced = false      // but was modified locally (status changed)
        o.createdAtDevice = Date.now()
      })
    })

    const payload = await buildPushPayload(db, DEVICE_ID)
    expect(payload.changes.orders.updated).toHaveLength(1)
    expect((payload.changes.orders.updated[0] as any).id).toBe('server-order-1')
    expect((payload.changes.orders.updated[0] as any).status).toBe('processing')
    // money fields must NOT be in the update payload
    expect((payload.changes.orders.updated[0] as any).total_kobo).toBeUndefined()
  })

  it('includes new customers with is_dirty=true', async () => {
    const db = makeDb()
    await db.write(async () => {
      await db.get<CustomerModel>('customers').create(c => {
        c._raw.id = 'new-customer-1'
        c.name = 'Ngozi Adeyemi'
        c.phone = '08099887766'
        c.tier = 1
        c.serverSeq = null
        c.isDirty = true
      })
    })

    const payload = await buildPushPayload(db, DEVICE_ID)
    expect(payload.changes.customers.created).toHaveLength(1)
    expect((payload.changes.customers.created[0] as any).name).toBe('Ngozi Adeyemi')
  })

  it('includes unsynced payments in created list', async () => {
    const db = makeDb()
    await db.write(async () => {
      await db.get<PaymentModel>('payments').create(p => {
        p._raw.id = 'pay-offline-1'
        p.orderId = 'some-order-id'
        p.amountKobo = 50_000
        p.method = 'cash'
        p.recordedAt = new Date().toISOString()
        p.serverSeq = null
        p.isSynced = false
      })
    })

    const payload = await buildPushPayload(db, DEVICE_ID)
    expect(payload.changes.payments.created).toHaveLength(1)
    expect((payload.changes.payments.created[0] as any).amount_kobo).toBe(50_000)
  })

  it('returns empty payload when nothing is dirty', async () => {
    const db = makeDb()
    const payload = await buildPushPayload(db, DEVICE_ID)
    expect(payload.changes.orders.created).toHaveLength(0)
    expect(payload.changes.orders.updated).toHaveLength(0)
    expect(payload.changes.customers.created).toHaveLength(0)
    expect(payload.changes.payments.created).toHaveLength(0)
  })
})
