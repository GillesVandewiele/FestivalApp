import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { db } from './schema'
import { markStockoutsSynced, pendingStockouts, soldOutIds, toggle } from './stockouts'

const AT = new Date('2026-07-01T22:00:00Z')
const LATER = new Date('2026-07-01T23:30:00Z')

beforeEach(async () => {
  await db.stockouts.clear()
})

describe('stockouts on the tablet', () => {
  it('marks a drink out', async () => {
    await toggle('p1', AT)
    expect([...(await soldOutIds())]).toEqual(['p1'])
  })

  it('puts it back with the same gesture', async () => {
    // Marking something out by accident must not cost the bar that drink all night.
    await toggle('p1', AT)
    const stillOut = await toggle('p1', LATER)

    expect(stillOut).toBe(false)
    expect([...(await soldOutIds())]).toEqual([])
  })

  it('closes the record rather than deleting it, so the report keeps the window', async () => {
    await toggle('p1', AT)
    await toggle('p1', LATER)

    const rows = await db.stockouts.toArray()
    expect(rows).toHaveLength(1)
    expect(rows[0].out_at).toBe(AT.toISOString())
    expect(rows[0].back_at).toBe(LATER.toISOString())
  })

  it('can go out again after coming back', async () => {
    await toggle('p1', AT)
    await toggle('p1', LATER)
    await toggle('p1', new Date('2026-07-02T01:00:00Z'))

    expect([...(await soldOutIds())]).toEqual(['p1'])
    expect(await db.stockouts.count()).toBe(2)
  })

  it('marking out twice does not create a second open record', async () => {
    await toggle('p1', AT)
    await db.stockouts.toArray()
    const { markOut } = await import('./stockouts')
    await markOut('p1', LATER)

    expect(await db.stockouts.count()).toBe(1)
  })

  it('queues for sync and stops once accepted', async () => {
    await toggle('p1', AT)
    const queued = await pendingStockouts()
    expect(queued).toHaveLength(1)
    expect(queued[0]).not.toHaveProperty('synced')

    await markStockoutsSynced([queued[0].id])
    expect(await pendingStockouts()).toHaveLength(0)
  })

  it('re-queues when a drink comes back, so the server learns the window closed', async () => {
    await toggle('p1', AT)
    const first = await pendingStockouts()
    await markStockoutsSynced([first[0].id])

    await toggle('p1', LATER)

    const again = await pendingStockouts()
    expect(again).toHaveLength(1)
    expect(again[0].id).toBe(first[0].id) // same record, now closed
    expect(again[0].back_at).toBe(LATER.toISOString())
  })

  it('tracks several drinks independently', async () => {
    await toggle('p1', AT)
    await toggle('p2', AT)
    await toggle('p1', LATER)

    expect([...(await soldOutIds())]).toEqual(['p2'])
  })
})
