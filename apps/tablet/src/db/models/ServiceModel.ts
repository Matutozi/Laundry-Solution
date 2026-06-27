import { Model } from '@nozbe/watermelondb'
import { field } from '@nozbe/watermelondb/decorators'

export class ServiceModel extends Model {
  static table = 'services'

  @field('name') name!: string
}
