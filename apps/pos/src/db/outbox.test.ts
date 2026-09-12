import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import type { OrderPayload } from '../api/client'
import { enqueue, markSynced, pending, pendingCount, recent, voidQueued } from './outbox'
import { db } from './schema'

function order(id: string): OrderPayload {
  return {
    id,
    edition_id: 'e1',
    bar_id: 'b1',
    staff_id: 's1',
    items: [{ product_id: 'p1', slug: 'jupiler', name: 'Jupiler', qty: 1, unit_price_coupons: 1 }],
    created_at: '2026-07-01T20:00:00+00:00',
    status: 'confirmed',
  }
}

beforeEach(async () => {
  await db.outbox.clear()
})

describe('outbox', () => {
  it('queues an order and reports it pending', async () => {
    await enqueue(order('a'))
    expect(await pendingCount()).toBe(1)
    expect((await pending()).map((o) => o.id)).toEqual(['a'])
  })

  it('stops reporting an order once synced', async () => {
    await enqueue(order('a'))
    await markSynced(['a'])
    expect(await pendingCount()).toBe(0)
  })

  it('keeps a synced order in recent history', async () => {
    await enqueue(order('a'))
    await markSynced(['a'])
    expect((await recent(10)).map((o) => o.id)).toEqual(['a'])
  })

  it('drops an order voided before it ever synced', async () => {
    await enqueue(order('a'))
    expect(await voidQueued('a', { type: 'staff', id: 's1' })).toBe('dropped-before-sync')
    expect(await pendingCount()).toBe(0)
  })

  it('queues a void for an order that already synced', async () => {
    await enqueue(order('a'))
    await markSynced(['a'])

    expect(await voidQueued('a', { type: 'staff', id: 's1' })).toBe('queued-void')

    const queued = await pending()
    expect(queued).toHaveLength(1)
    expect(queued[0].status).toBe('voided')
    expect(queued[0].void?.by.id).toBe('s1')
  })

  it('returns not-found for an unknown id', async () => {
    expect(await voidQueued('nope', { type: 'staff', id: 's1' })).toBe('not-found')
  })

  it('returns pending orders oldest first so the queue drains in order', async () => {
    await enqueue({ ...order('a'), created_at: '2026-07-01T20:00:00+00:00' })
    await enqueue({ ...order('b'), created_at: '2026-07-01T19:00:00+00:00' })
    expect((await pending()).map((o) => o.id)).toEqual(['b', 'a'])
  })

  it('never puts the internal synced flag on the wire', async () => {
    await enqueue(order('a'))
    expect(await pending()).toEqual([order('a')])
  })
})
