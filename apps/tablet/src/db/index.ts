import { Database } from '@nozbe/watermelondb'
import type { DatabaseAdapter } from '@nozbe/watermelondb/adapters/type'
import { schema } from './schema'
import {
  CustomerModel,
  OrderModel,
  OrderLineModel,
  PaymentModel,
  PriceRuleModel,
  ServiceModel,
  SettingModel,
} from './models'

const MODEL_CLASSES = [
  CustomerModel,
  OrderModel,
  OrderLineModel,
  PaymentModel,
  PriceRuleModel,
  ServiceModel,
  SettingModel,
]

export function makeDatabase(adapter: DatabaseAdapter): Database {
  return new Database({ adapter, modelClasses: MODEL_CLASSES })
}

// Production singleton — created lazily so tests can call makeDatabase() instead
let _db: Database | null = null

export function getDatabase(): Database {
  if (!_db) {
    // SQLiteAdapter is only imported here so Jest (which uses LokiJS) never touches native code
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const SQLiteAdapter = require('@nozbe/watermelondb/adapters/sqlite').default
    const adapter = new SQLiteAdapter({ schema, jsi: true })
    _db = makeDatabase(adapter)
  }
  return _db
}
