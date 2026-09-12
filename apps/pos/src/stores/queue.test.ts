import 'fake-indexeddb/auto'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type OrderPayload } from '../api/client'
import { enqueue, pendingCount } from '../db/outbox'
import { db } from '../db/schema'
import { useQueue } from './queue'

function order(id: string): OrderPayload {
  return {
    id,
    edition_id: 'e1',
    bar_id: 'b1',
    staff_id: 's1',
    items: [{ product_id: 'p1', slug: 'jupiler', name: 'Jupiler', qty: 1, unit_price_coupons: 1 }],
    created_at: '2026-07-01T20:00:00+00:00',
    status: 'confirmed',
    kind: 'sale',
  }
}

beforeEach(async () => {
  setActivePinia(createPinia())
  await db.outbox.clear()
})

describe('sync worker', () => {
  it('clears the queue when the server accepts', async () => {
    await enqueue(order('a'))
    const queue = useQueue()
    queue.client = { syncOrders: vi.fn().mockResolvedValue({ accepted: ['a'], results: {} }) }

    await queue.drain()

    expect(await pendingCount()).toBe(0)
  })

  it('keeps the order queued when the network fails', async () => {
    await enqueue(order('a'))
    const queue = useQueue()
    queue.client = { syncOrders: vi.fn().mockRejectedValue(new Error('offline')) }

    await queue.drain()

    expect(await pendingCount()).toBe(1)
    expect(queue.online).toBe(false)
  })

  it('only clears the ids the server actually accepted', async () => {
    await enqueue(order('a'))
    await enqueue(order('b'))
    const queue = useQueue()
    queue.client = {
      syncOrders: vi.fn().mockResolvedValue({ accepted: ['a'], results: { b: 'rejected' } }),
    }

    await queue.drain()

    expect(await pendingCount()).toBe(1)
  })

  it('does not run two drains at once', async () => {
    await enqueue(order('a'))
    const queue = useQueue()
    const syncOrders = vi
      .fn()
      .mockImplementation(
        () => new Promise((r) => setTimeout(() => r({ accepted: ['a'], results: {} }), 20)),
      )
    queue.client = { syncOrders }

    await Promise.all([queue.drain(), queue.drain()])

    expect(syncOrders).toHaveBeenCalledTimes(1)
  })

  it('reports back online after a failure once the network returns', async () => {
    await enqueue(order('a'))
    const queue = useQueue()
    queue.client = { syncOrders: vi.fn().mockRejectedValue(new Error('offline')) }
    await queue.drain()
    expect(queue.online).toBe(false)

    queue.client = { syncOrders: vi.fn().mockResolvedValue({ accepted: ['a'], results: {} }) }
    await queue.drain()

    expect(queue.online).toBe(true)
    expect(await pendingCount()).toBe(0)
  })
})

describe('sync worker, when the server rejects the code', () => {
  it('stops retrying a code the server no longer recognises', async () => {
    // Retrying cannot fix a revoked code, and at one attempt every five seconds it
    // trips the server's guess limit, which blocks every tablet on the same wifi.
    await enqueue(order('a'))
    const queue = useQueue()
    const syncOrders = vi.fn().mockRejectedValue(new ApiError(401, 'nope'))
    queue.client = { syncOrders }

    await queue.drain()
    await queue.drain()
    await queue.drain()

    expect(syncOrders).toHaveBeenCalledTimes(1)
    expect(queue.unlinked).toBe(true)
  })

  it('does not call an unlinked tablet offline', async () => {
    await enqueue(order('a'))
    const queue = useQueue()
    queue.client = { syncOrders: vi.fn().mockRejectedValue(new ApiError(401, 'nope')) }

    await queue.drain()

    expect(queue.unlinked).toBe(true)
    expect(queue.online).toBe(true) // the network is fine; the code is not
  })

  it('keeps queued orders when the tablet is unlinked', async () => {
    await enqueue(order('a'))
    const queue = useQueue()
    queue.client = { syncOrders: vi.fn().mockRejectedValue(new ApiError(401, 'nope')) }

    await queue.drain()

    expect(await pendingCount()).toBe(1)
  })

  it('backs off instead of hammering when the address is throttled', async () => {
    await enqueue(order('a'))
    const queue = useQueue()
    const syncOrders = vi.fn().mockRejectedValue(new ApiError(429, 'slow down'))
    queue.client = { syncOrders }

    await queue.drain()
    await queue.drain()

    expect(syncOrders).toHaveBeenCalledTimes(1)
    expect(queue.unlinked).toBe(false)
  })

  it('resumes after re-linking, with the queue intact', async () => {
    await enqueue(order('a'))
    const queue = useQueue()
    queue.client = { syncOrders: vi.fn().mockRejectedValue(new ApiError(401, 'nope')) }
    await queue.drain()

    queue.client = { syncOrders: vi.fn().mockResolvedValue({ accepted: ['a'], results: {} }) }
    await queue.relinked()

    expect(queue.unlinked).toBe(false)
    expect(await pendingCount()).toBe(0)
  })

  it('still reports a genuine network failure as offline', async () => {
    await enqueue(order('a'))
    const queue = useQueue()
    queue.client = { syncOrders: vi.fn().mockRejectedValue(new TypeError('fetch failed')) }

    await queue.drain()

    expect(queue.online).toBe(false)
    expect(queue.unlinked).toBe(false)
  })
})
