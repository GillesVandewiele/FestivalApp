import { describe, expect, it, vi } from 'vitest'
import { ApiError, createClient } from './client'

describe('api client', () => {
  it('sends the device token as a bearer header', async () => {
    const fetchSpy = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ server_time: '2026-07-01T20:00:00+00:00' }), { status: 200 }),
      )
    const client = createClient('http://api.test', () => 'tok-123', fetchSpy)

    await client.getTime()

    const init = fetchSpy.mock.calls[0][1]
    expect(init.headers.Authorization).toBe('Bearer tok-123')
  })

  it('omits the header when there is no token', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    const client = createClient('http://api.test', () => null, fetchSpy)

    await client.getTime()

    expect(fetchSpy.mock.calls[0][1].headers.Authorization).toBeUndefined()
  })

  it('throws ApiError carrying the status on a failure', async () => {
    // A Response body can only be read once, so build a fresh one per call.
    const fetchSpy = vi.fn().mockImplementation(async () => new Response('nope', { status: 401 }))
    const client = createClient('http://api.test', () => 'tok', fetchSpy)

    await expect(client.getTime()).rejects.toBeInstanceOf(ApiError)
    await expect(client.getTime()).rejects.toMatchObject({ status: 401 })
  })

  it('posts orders to the sync endpoint', async () => {
    const fetchSpy = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ accepted: ['a'], results: { a: 'inserted' } }), {
          status: 200,
        }),
      )
    const client = createClient('http://api.test', () => 'tok', fetchSpy)

    const result = await client.syncOrders([{ id: 'a' } as never])

    expect(fetchSpy.mock.calls[0][0]).toBe('http://api.test/api/v1/sync/orders')
    expect(result.accepted).toEqual(['a'])
  })
})
