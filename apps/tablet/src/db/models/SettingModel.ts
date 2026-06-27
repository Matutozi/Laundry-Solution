import { Model } from '@nozbe/watermelondb'
import { field } from '@nozbe/watermelondb/decorators'

// Record id IS the key (e.g. id="last_server_seq", value="42")
export class SettingModel extends Model {
  static table = 'settings'

  @field('value') value!: string
}
