import { Model } from '@nozbe/watermelondb'
import { field } from '@nozbe/watermelondb/decorators'

export class OrderLineModel extends Model {
  static table = 'order_lines'
  static associations = {
    orders: { type: 'belongs_to' as const, key: 'order_id' },
  }

  @field('order_id') orderId!: string
  @field('service_id') serviceId!: string
  @field('piece_count') pieceCount!: number
  @field('unit_price_kobo') unitPriceKobo!: number
  @field('line_total_kobo') lineTotalKobo!: number
}
