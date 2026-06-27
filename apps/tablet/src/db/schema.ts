import { appSchema, tableSchema } from '@nozbe/watermelondb'

export const schema = appSchema({
  version: 1,
  tables: [
    tableSchema({
      name: 'customers',
      columns: [
        { name: 'name', type: 'string' },
        { name: 'phone', type: 'string', isIndexed: true },
        { name: 'tier', type: 'number' },
        { name: 'server_seq', type: 'number', isOptional: true },
        { name: 'is_dirty', type: 'boolean' },
      ],
    }),
    tableSchema({
      name: 'orders',
      columns: [
        { name: 'branch_id', type: 'string', isIndexed: true },
        { name: 'attendant_id', type: 'string', isIndexed: true },
        { name: 'customer_id', type: 'string', isIndexed: true },
        { name: 'status', type: 'string' },
        { name: 'turnaround', type: 'string' },
        { name: 'pickup_code', type: 'string', isIndexed: true },
        { name: 'total_kobo', type: 'number' },
        { name: 'version', type: 'number' },
        { name: 'server_seq', type: 'number', isOptional: true },
        { name: 'is_synced', type: 'boolean' },
        { name: 'created_at_device', type: 'number' },
      ],
    }),
    tableSchema({
      name: 'order_lines',
      columns: [
        { name: 'order_id', type: 'string', isIndexed: true },
        { name: 'service_id', type: 'string' },
        { name: 'piece_count', type: 'number' },
        { name: 'unit_price_kobo', type: 'number' },
        { name: 'line_total_kobo', type: 'number' },
      ],
    }),
    tableSchema({
      name: 'payments',
      columns: [
        { name: 'order_id', type: 'string', isIndexed: true },
        { name: 'amount_kobo', type: 'number' },
        { name: 'method', type: 'string' },
        { name: 'recorded_at', type: 'string' },
        { name: 'server_seq', type: 'number', isOptional: true },
        { name: 'is_synced', type: 'boolean' },
      ],
    }),
    tableSchema({
      name: 'services',
      columns: [
        { name: 'name', type: 'string' },
      ],
    }),
    tableSchema({
      name: 'price_rules',
      columns: [
        { name: 'service_id', type: 'string', isIndexed: true },
        { name: 'tier', type: 'number' },
        { name: 'price_kobo', type: 'number' },
      ],
    }),
    // key/value store: record id IS the key (e.g. "last_server_seq")
    tableSchema({
      name: 'settings',
      columns: [
        { name: 'value', type: 'string' },
      ],
    }),
  ],
})
