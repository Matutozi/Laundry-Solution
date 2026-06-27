import { Model } from '@nozbe/watermelondb'
import { field } from '@nozbe/watermelondb/decorators'

export class PaymentModel extends Model {
  static table = 'payments'
  static associations = {
    orders: { type: 'belongs_to' as const, key: 'order_id' },
  }

  @field('order_id') orderId!: string
  @field('amount_kobo') amountKobo!: number
  @field('method') method!: string
  @field('recorded_at') recordedAt!: string
  @field('server_seq') serverSeq!: number | null
  @field('is_synced') isSynced!: boolean
}
