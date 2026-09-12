import type { StockoutPayload } from '../api/client'
import { db } from './schema'

/**
 * Which drinks have run out, kept on the tablet so it works offline like everything
 * else.
 *
 * A stockout is a record with an `out_at` and, once the drink is back, a `back_at`.
 * Marking something back in stock closes the existing record rather than deleting it,
 * because the report needs to know demand was cut off between those two times.
 *
 * Every state here is reversible by the same gesture that set it. Marking a drink
 * sold out by accident must not cost the bar that product for the night.
 */

export async function markOut(productId: string, at: Date): Promise<void> {
  const open = await currentRecord(productId)
  if (open) return // already out; nothing to do

  await db.stockouts.put({
    id: crypto.randomUUID(),
    product_id: productId,
    out_at: at.toISOString(),
    back_at: null,
    synced: 0,
  })
}

export async function markBack(productId: string, at: Date): Promise<void> {
  const open = await currentRecord(productId)
  if (!open) return

  await db.stockouts.put({ ...open, back_at: at.toISOString(), synced: 0 })
}

export async function toggle(productId: string, at: Date): Promise<boolean> {
  const open = await currentRecord(productId)
  if (open) {
    await markBack(productId, at)
    return false
  }
  await markOut(productId, at)
  return true
}

/** Product ids that are out right now. */
export async function soldOutIds(): Promise<Set<string>> {
  const rows = await db.stockouts.toArray()
  const out = new Set<string>()
  for (const r of rows) {
    if (r.back_at === null) out.add(r.product_id)
    else out.delete(r.product_id)
  }
  return out
}

export async function pendingStockouts(): Promise<StockoutPayload[]> {
  const rows = await db.stockouts.where('synced').equals(0).toArray()
  return rows.map(({ synced: _synced, ...rest }) => rest)
}

export async function markStockoutsSynced(ids: string[]): Promise<void> {
  await db.stockouts.where('id').anyOf(ids).modify({ synced: 1 })
}

async function currentRecord(productId: string) {
  const rows = await db.stockouts.where('product_id').equals(productId).toArray()
  const open = rows.filter((r) => r.back_at === null)
  // Newest wins if a tablet somehow recorded two: the later one is the live state.
  return open.sort((a, b) => b.out_at.localeCompare(a.out_at))[0]
}
