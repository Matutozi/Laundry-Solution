import { Database } from '@nozbe/watermelondb'
import LokiJSAdapter from '@nozbe/watermelondb/adapters/lokijs'
import { schema } from '../../src/db/schema'
import {
  CustomerModel,
  OrderModel,
  OrderLineModel,
  PaymentModel,
  PriceRuleModel,
  ServiceModel,
  SettingModel,
} from '../../src/db/models'

const MODEL_CLASSES = [
  CustomerModel,
  OrderModel,
  OrderLineModel,
  PaymentModel,
  PriceRuleModel,
  ServiceModel,
  SettingModel,
]

export function makeDb(): Database {
  const adapter = new LokiJSAdapter({
    schema,
    useWebWorker: false,
    useIncrementalIndexedDB: false,
  })
  return new Database({ adapter, modelClasses: MODEL_CLASSES })
}
