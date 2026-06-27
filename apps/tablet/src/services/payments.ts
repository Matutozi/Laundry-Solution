import { Database, Q } from '@nozbe/watermelondb'
import { PaymentModel } from '../db/models/PaymentModel'

export type PaymentMethod = 'cash' | 'transfer' | 'pos'

export async function recordPaymentLocally(
  db: Database,
  id: string,
  orderId: string,
  amountKobo: number,
  method: PaymentMethod,
): Promise<PaymentModel> {
  return db.write(async () =>
    db.get<PaymentModel>('payments').create(p => {
      p._raw.id = id
      p.orderId = orderId
      p.amountKobo = amountKobo
      p.method = method
      p.recordedAt = new Date().toISOString()
      p.serverSeq = null
      p.isSynced = false
    }),
  )
}

export async function getTotalPaidKobo(
  db: Database,
  orderId: string,
): Promise<number> {
  const payments = await db
    .get<PaymentModel>('payments')
    .query(Q.where('order_id', orderId))
    .fetch()
  return payments.reduce((sum, p) => sum + p.amountKobo, 0)
}
