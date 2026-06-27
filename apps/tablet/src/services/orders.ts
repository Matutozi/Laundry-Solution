import { Database, Q } from '@nozbe/watermelondb'
import { CustomerModel } from '../db/models/CustomerModel'
import { OrderModel } from '../db/models/OrderModel'
import { OrderLineModel } from '../db/models/OrderLineModel'
import { computeOrderTotal, type LineInput, type Turnaround } from './pricing'

const ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

function randomChars(n: number): string {
  let out = ''
  for (let i = 0; i < n; i++) {
    out += ALPHA[Math.floor(Math.random() * ALPHA.length)]
  }
  return out
}

/**
 * Generate an offline pickup code that embeds branch + device identity so
 * two devices from the same branch can't produce the same code without a
 * random collision. Mirrors the server's offline_pickup_code() function.
 *
 * Format: <3 branch chars><3 device chars><5 random chars> = 11 chars
 */
export function generateOfflinePickupCode(branchId: string, deviceId: string): string {
  const branchPrefix = branchId.replace(/-/g, '').slice(0, 3).toUpperCase()
  const devicePrefix = deviceId.replace(/-/g, '').slice(0, 3).toUpperCase()
  return `${branchPrefix}${devicePrefix}${randomChars(5)}`
}

export interface CreateOrderParams {
  id: string           // caller-supplied UUID (so it can be stored and referenced)
  branchId: string
  attendantId: string
  customerId: string
  turnaround: Turnaround
  lines: LineInput[]
  deviceId: string
  customerTier: number
  rules: Array<{ serviceId: string; tier: number; priceKobo: number }>
}

export async function createOrderLocally(
  db: Database,
  params: CreateOrderParams,
): Promise<OrderModel> {
  const { lines: pricedLines, totalKobo } = computeOrderTotal(
    params.lines,
    params.customerTier,
    params.turnaround,
    params.rules,
  )
  const pickupCode = generateOfflinePickupCode(params.branchId, params.deviceId)

  return db.write(async () => {
    const order = await db.get<OrderModel>('orders').create(o => {
      o._raw.id = params.id
      o.branchId = params.branchId
      o.attendantId = params.attendantId
      o.customerId = params.customerId
      o.status = 'received'
      o.turnaround = params.turnaround
      o.pickupCode = pickupCode
      o.totalKobo = totalKobo
      o.version = 1
      o.serverSeq = null
      o.isSynced = false
      o.createdAtDevice = Date.now()
    })

    for (const line of pricedLines) {
      await db.get<OrderLineModel>('order_lines').create(l => {
        l.orderId = order.id
        l.serviceId = line.serviceId
        l.pieceCount = line.pieceCount
        l.unitPriceKobo = line.unitPriceKobo
        l.lineTotalKobo = line.lineTotalKobo
      })
    }

    return order
  })
}

export async function updateOrderStatusLocally(
  db: Database,
  order: OrderModel,
  status: string,
): Promise<void> {
  await db.write(async () => {
    await order.update(o => {
      o.status = status
      o.version += 1
      o.isSynced = false
    })
  })
}

export async function updatePickupCodeAfterSync(
  db: Database,
  order: OrderModel,
  newCode: string,
  serverTotal: number,
): Promise<void> {
  await db.write(async () => {
    await order.update(o => {
      o.pickupCode = newCode
      o.totalKobo = serverTotal
      o.isSynced = true
    })
  })
}

export async function findCustomerByPhone(
  db: Database,
  phone: string,
): Promise<CustomerModel | null> {
  const results = await db
    .get<CustomerModel>('customers')
    .query(Q.where('phone', phone))
    .fetch()
  return results[0] ?? null
}

export async function createCustomerLocally(
  db: Database,
  id: string,
  name: string,
  phone: string,
  tier = 1,
): Promise<CustomerModel> {
  return db.write(async () =>
    db.get<CustomerModel>('customers').create(c => {
      c._raw.id = id
      c.name = name
      c.phone = phone
      c.tier = tier
      c.serverSeq = null
      c.isDirty = true
    }),
  )
}
