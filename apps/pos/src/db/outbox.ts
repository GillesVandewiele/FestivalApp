import type { OrderPayload } from '../api/client'
import { db, type OutboxRow } from './schema'

export async function enqueue(order: OrderPayload): Promise<void> {
  await db.outbox.put({ ...order, synced: 0 })
}

export async function pending(limit = 100): Promise<OrderPayload[]> {
  const rows = await db.outbox.where('synced').equals(0).sortBy('created_at')
  return rows.slice(0, limit).map(strip)
}

export async function pendingCount(): Promise<number> {
  return db.outbox.where('synced').equals(0).count()
}

export async function markSynced(ids: string[]): Promise<void> {
  await db.outbox.where('id').anyOf(ids).modify({ synced: 1 })
}

export async function recent(limit: number): Promise<OrderPayload[]> {
  const rows = await db.outbox.orderBy('created_at').reverse().limit(limit).toArray()
  return rows.map(strip)
}

/**
 * Void an order the tablet has already committed.
 *
 * If it never reached the server there is nothing to correct, so it is simply dropped:
 * one fewer write and no orphan record. If it did sync, the same document is re-queued
 * with status "voided". The server upserts on the id and treats confirmed-to-voided as
 * a one-way transition, so this is safe to retry.
 */
export async function voidQueued(
  id: string,
  by: { type: 'staff'; id: string },
): Promise<'dropped-before-sync' | 'queued-void' | 'not-found'> {
  const row = await db.outbox.get(id)
  if (!row) return 'not-found'

  if (row.synced === 0) {
    await db.outbox.delete(id)
    return 'dropped-before-sync'
  }

  await db.outbox.put({
    ...row,
    synced: 0,
    status: 'voided',
    void: { at: new Date().toISOString(), by, reason: null },
  })
  return 'queued-void'
}

function strip(row: OutboxRow): OrderPayload {
  const { synced: _synced, ...order } = row
  return order
}
