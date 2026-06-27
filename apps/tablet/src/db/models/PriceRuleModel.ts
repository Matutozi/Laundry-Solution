import { Model } from '@nozbe/watermelondb'
import { field } from '@nozbe/watermelondb/decorators'

export class PriceRuleModel extends Model {
  static table = 'price_rules'

  @field('service_id') serviceId!: string
  @field('tier') tier!: number
  @field('price_kobo') priceKobo!: number
}
