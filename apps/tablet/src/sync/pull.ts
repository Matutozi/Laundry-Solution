import type { Database } from '@nozbe/watermelondb'
import { CustomerModel } from '../db/models/CustomerModel'
import { OrderModel } from '../db/models/OrderModel'
import { PaymentModel } from '../db/models/PaymentModel'
import { ServiceModel } from '../db/models/ServiceModel'
import { PriceRuleModel } from '../db/models/PriceRuleModel'
import { SettingModel } from '../db/models/SettingModel'
import type { ApiClient } from '../api/client'

interface PullResponse {
  changes: {
    orders: ServerOrder[]
    payments: ServerPayment[]
    customers: ServerCustomer[]
  }
  server_seq: number
}

interface ServerOrder {
  id: string
  branch_id: string
  attendant_id: string
  customer_id: string
  status: string
  turnaround: string
  pickup_code: string
  total_kobo: number
  version: number
  server_seq: number
}

interface ServerPayment {
  id: string
  order_id: string
  amount_kobo: number
  method: string
  recorded_at: string
  server_seq: number
}

interface ServerCustomer {
  id: string
  name: string
  phone: string
  tier: number
  server_seq: number
}

export async function getLastServerSeq(db: Database): Promise<number> {
  const setting = await db.get<SettingModel>('settings').find('last_server_seq').catch(() => null)
  return setting ? parseInt(setting.value, 10) : 0
}

async function setLastServerSeq(db: Database, seq: number): Promise<void> {
  await db.write(async () => {
    const existing = await db
      .get<SettingModel>('settings')
      .find('last_server_seq')
      .catch(() => null)
    if (existing) {
      await existing.update(s => { s.value = String(seq) })
    } else {
      await db.get<SettingModel>('settings').create(s => {
        s._raw.id = 'last_server_seq'
        s.value = String(seq)
      })
    }
  })
}

async function upsertOrder(db: Database, o: ServerOrder): Promise<void> {
  const existing = await db.get<OrderModel>('orders').find(o.id).catch(() => null)
  if (existing) {
    await existing.update(record => {
      record.status = o.status
      record.pickupCode = o.pickup_code
      record.totalKobo = o.total_kobo
      record.version = o.version
      record.serverSeq = o.server_seq
      record.isSynced = true
    })
  } else {
    await db.get<OrderModel>('orders').create(record => {
      record._raw.id = o.id
      record.branchId = o.branch_id
      record.attendantId = o.attendant_id
      record.customerId = o.customer_id
      record.status = o.status
      record.turnaround = o.turnaround
      record.pickupCode = o.pickup_code
      record.totalKobo = o.total_kobo
      record.version = o.version
      record.serverSeq = o.server_seq
      record.isSynced = true
      record.createdAtDevice = Date.now()
    })
  }
}

async function upsertPayment(db: Database, p: ServerPayment): Promise<void> {
  const existing = await db.get<PaymentModel>('payments').find(p.id).catch(() => null)
  if (existing) return // payments are immutable once on server
  await db.get<PaymentModel>('payments').create(record => {
    record._raw.id = p.id
    record.orderId = p.order_id
    record.amountKobo = p.amount_kobo
    record.method = p.method
    record.recordedAt = p.recorded_at
    record.serverSeq = p.server_seq
    record.isSynced = true
  })
}

async function upsertCustomer(db: Database, c: ServerCustomer): Promise<void> {
  const existing = await db.get<CustomerModel>('customers').find(c.id).catch(() => null)
  if (existing) {
    await existing.update(record => {
      record.name = c.name
      record.tier = c.tier
      record.serverSeq = c.server_seq
      record.isDirty = false
    })
  } else {
    await db.get<CustomerModel>('customers').create(record => {
      record._raw.id = c.id
      record.name = c.name
      record.phone = c.phone
      record.tier = c.tier
      record.serverSeq = c.server_seq
      record.isDirty = false
    })
  }
}

export async function applyPull(db: Database, api: ApiClient): Promise<number> {
  const since = await getLastServerSeq(db)
  const { changes, server_seq } = await api.get<PullResponse>(`/sync/pull?since=${since}`)

  await db.write(async () => {
    for (const o of changes.orders) await upsertOrder(db, o)
    for (const p of changes.payments) await upsertPayment(db, p)
    for (const c of changes.customers) await upsertCustomer(db, c)
  })

  await setLastServerSeq(db, server_seq)
  return server_seq
}

// ── Pricing bootstrap (separate from order sync) ──────────────────────────────

interface PricingResponse {
  services: Array<{ id: string; name: string }>
  rules: Array<{ service_id: string; tier: number; price_kobo: number }>
}

export async function seedPricing(db: Database, api: ApiClient): Promise<void> {
  const { services, rules } = await api.get<PricingResponse>('/admin/pricing')

  await db.write(async () => {
    for (const svc of services) {
      const existing = await db
        .get<ServiceModel>('services')
        .find(svc.id)
        .catch(() => null)
      if (existing) {
        await existing.update(s => { s.name = svc.name })
      } else {
        await db.get<ServiceModel>('services').create(s => {
          s._raw.id = svc.id
          s.name = svc.name
        })
      }
    }

    for (const rule of rules) {
      const ruleId = `${rule.service_id}:${rule.tier}`
      const existing = await db
        .get<PriceRuleModel>('price_rules')
        .find(ruleId)
        .catch(() => null)
      if (existing) {
        await existing.update(r => { r.priceKobo = rule.price_kobo })
      } else {
        await db.get<PriceRuleModel>('price_rules').create(r => {
          r._raw.id = ruleId
          r.serviceId = rule.service_id
          r.tier = rule.tier
          r.priceKobo = rule.price_kobo
        })
      }
    }
  })
}
