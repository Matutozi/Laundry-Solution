import { Model } from '@nozbe/watermelondb'
import { children, field } from '@nozbe/watermelondb/decorators'
import type { Query } from '@nozbe/watermelondb'
import type { OrderLineModel } from './OrderLineModel'
import type { PaymentModel } from './PaymentModel'

export class OrderModel extends Model {
  static table = 'orders'
  static associations = {
    order_lines: { type: 'has_many' as const, foreignKey: 'order_id' },
    payments: { type: 'has_many' as const, foreignKey: 'order_id' },
  }

  @field('branch_id') branchId!: string
  @field('attendant_id') attendantId!: string
  @field('customer_id') customerId!: string
  @field('status') status!: string
  @field('turnaround') turnaround!: string
  @field('pickup_code') pickupCode!: string
  @field('total_kobo') totalKobo!: number
  @field('version') version!: number
  @field('server_seq') serverSeq!: number | null
  @field('is_synced') isSynced!: boolean
  @field('created_at_device') createdAtDevice!: number

  @children('order_lines') lines!: Query<OrderLineModel>
  @children('payments') payments!: Query<PaymentModel>
}
