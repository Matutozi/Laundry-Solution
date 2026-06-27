import { Model } from '@nozbe/watermelondb'
import { field } from '@nozbe/watermelondb/decorators'

export class CustomerModel extends Model {
  static table = 'customers'

  @field('name') name!: string
  @field('phone') phone!: string
  @field('tier') tier!: number
  @field('server_seq') serverSeq!: number | null
  @field('is_dirty') isDirty!: boolean
}
