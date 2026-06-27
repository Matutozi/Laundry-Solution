import type { Database } from '@nozbe/watermelondb'
import { Q } from '@nozbe/watermelondb'
import { CustomerModel } from '../db/models/CustomerModel'
import { OrderModel } from '../db/models/OrderModel'
import { OrderLineModel } from '../db/models/OrderLineModel'
import { PaymentModel } from '../db/models/PaymentModel'
import type { ApiClient } from '../api/client'

interface PushResponse {
  reassigned_codes: Record<string, string>
  server_seq: number
}

export interface PushPayload {
  device_id: string
  changes: {
    customers: { created: unknown[]; updated: unknown[] }
    orders: { created: unknown[]; updated: unknown[] }
    payments: { created: unknown[] }
  }
}

export async function buildPushPayload(
  db: Database,
  deviceId: string,
): Promise<PushPayload> {
  const dirtyCustomers = await db
    .get<CustomerModel>('customers')
    .query(Q.where('is_dirty', true))
    .fetch()

  const unsyncedOrders = await db
    .get<OrderModel>('orders')
    .query(Q.where('is_synced', false))
    .fetch()

  const unsyncedPayments = await db
    .get<PaymentModel>('payments')
    .query(Q.where('is_synced', false))
    .fetch()

  // Customers with no server_seq are new; otherwise they're updates
  const newCustomers = dirtyCustomers
    .filter(c => c.serverSeq == null)
    .map(c => ({ id: c.id, name: c.name, phone: c.phone, tier: c.tier }))

  const updatedCustomers = dirtyCustomers
    .filter(c => c.serverSeq != null)
    .map(c => ({ id: c.id, name: c.name, tier: c.tier }))

  // Orders with no server_seq are new (offline created); others are status updates
  const newOrders = await Promise.all(
    unsyncedOrders
      .filter(o => o.serverSeq == null)
      .map(async o => {
        const lines = await db
          .get<OrderLineModel>('order_lines')
          .query(Q.where('order_id', o.id))
          .fetch()
        return {
          id: o.id,
          branch_id: o.branchId,
          attendant_id: o.attendantId,
          customer_id: o.customerId,
          turnaround: o.turnaround,
          pickup_code: o.pickupCode,
          total_kobo: o.totalKobo,
          status: o.status,
          lines: lines.map(l => ({
            service_id: l.serviceId,
            piece_count: l.pieceCount,
          })),
        }
      }),
  )

  const updatedOrders = unsyncedOrders
    .filter(o => o.serverSeq != null)
    .map(o => ({ id: o.id, status: o.status }))

  const newPayments = unsyncedPayments.map(p => ({
    id: p.id,
    order_id: p.orderId,
    amount_kobo: p.amountKobo,
    method: p.method,
  }))

  return {
    device_id: deviceId,
    changes: {
      customers: { created: newCustomers, updated: updatedCustomers },
      orders: { created: newOrders, updated: updatedOrders },
      payments: { created: newPayments },
    },
  }
}

async function applyReassignedCodes(
  db: Database,
  reassigned: Record<string, string>,
  serverSeq: number,
): Promise<void> {
  if (Object.keys(reassigned).length === 0) return

  await db.write(async () => {
    for (const [oldCode, newCode] of Object.entries(reassigned)) {
      const orders = await db
        .get<OrderModel>('orders')
        .query(Q.where('pickup_code', oldCode))
        .fetch()
      for (const o of orders) {
        await o.update(record => {
          record.pickupCode = newCode
          record.isSynced = true
          record.serverSeq = serverSeq
        })
      }
    }
  })
}

async function markSynced(db: Database, serverSeq: number): Promise<void> {
  await db.write(async () => {
    const orders = await db
      .get<OrderModel>('orders')
      .query(Q.where('is_synced', false))
      .fetch()
    for (const o of orders) {
      await o.update(r => { r.isSynced = true; r.serverSeq = serverSeq })
    }

    const payments = await db
      .get<PaymentModel>('payments')
      .query(Q.where('is_synced', false))
      .fetch()
    for (const p of payments) {
      await p.update(r => { r.isSynced = true; r.serverSeq = serverSeq })
    }

    const customers = await db
      .get<CustomerModel>('customers')
      .query(Q.where('is_dirty', true))
      .fetch()
    for (const c of customers) {
      await c.update(r => { r.isDirty = false; r.serverSeq = serverSeq })
    }
  })
}

export async function executePush(
  db: Database,
  api: ApiClient,
  deviceId: string,
): Promise<PushResponse> {
  const payload = await buildPushPayload(db, deviceId)
  const hasChanges =
    payload.changes.customers.created.length > 0 ||
    payload.changes.customers.updated.length > 0 ||
    payload.changes.orders.created.length > 0 ||
    payload.changes.orders.updated.length > 0 ||
    payload.changes.payments.created.length > 0

  if (!hasChanges) return { reassigned_codes: {}, server_seq: 0 }

  const response = await api.post<PushResponse>('/sync/push', payload)
  await applyReassignedCodes(db, response.reassigned_codes, response.server_seq)
  await markSynced(db, response.server_seq)
  return response
}
