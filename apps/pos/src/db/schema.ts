import Dexie, { type EntityTable } from 'dexie'
import type { OrderPayload, StockoutPayload } from '../api/client'

export interface OutboxRow extends OrderPayload {
  synced: 0 | 1 // Dexie cannot index booleans
}

export interface MetaRow {
  key: string
  value: unknown
}

const db = new Dexie('festival-pos') as Dexie & {
  outbox: EntityTable<OutboxRow, 'id'>
  stockouts: EntityTable<StockoutPayload & { synced: 0 | 1 }, 'id'>
  meta: EntityTable<MetaRow, 'key'>
}

db.version(1).stores({
  outbox: 'id, synced, created_at',
  stockouts: 'id, synced',
  meta: 'key',
})

// A tablet that has already been used has version 1 on disk, so the added index has
// to arrive as a new version or Dexie will never build it.
db.version(2).stores({
  outbox: 'id, synced, created_at',
  stockouts: 'id, synced, product_id',
  meta: 'key',
})

export { db }
