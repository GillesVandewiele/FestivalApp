import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useCart } from './cart'
import type { Product } from './session'

const jupiler: Product = {
  id: 'p1',
  slug: 'jupiler',
  name: 'Jupiler',
  category: 'bier',
  price_coupons: 1,
  sort_order: 0,
}
const gin: Product = {
  id: 'p2',
  slug: 'gin-tonic',
  name: 'Gin-Tonic',
  category: 'cocktail',
  price_coupons: 4,
  sort_order: 1,
}

beforeEach(() => setActivePinia(createPinia()))

describe('cart', () => {
  it('starts empty', () => {
    const cart = useCart()
    expect(cart.isEmpty).toBe(true)
    expect(cart.totalCoupons).toBe(0)
  })

  it('increments the count when the same product is tapped again', () => {
    const cart = useCart()
    cart.add(jupiler)
    cart.add(jupiler)
    cart.add(jupiler)
    expect(cart.lines).toHaveLength(1)
    expect(cart.lines[0].qty).toBe(3)
  })

  it('totals a mixed round', () => {
    // 3 pintjes at 1 + 2 gin-tonics at 4 = 11 bonnetjes
    const cart = useCart()
    cart.add(jupiler)
    cart.add(jupiler)
    cart.add(jupiler)
    cart.add(gin)
    cart.add(gin)
    expect(cart.totalCoupons).toBe(11)
  })

  it('decrements on remove and drops the line at zero', () => {
    const cart = useCart()
    cart.add(jupiler)
    cart.add(jupiler)
    cart.remove('p1')
    expect(cart.lines[0].qty).toBe(1)
    cart.remove('p1')
    expect(cart.lines).toHaveLength(0)
  })

  it('builds an order payload with a fresh uuid and snapshotted prices', () => {
    const cart = useCart()
    cart.add(jupiler)
    cart.add(gin)

    const at = new Date('2026-07-01T20:00:00Z')
    const order = cart.buildOrder({ editionId: 'e1', barId: 'b1', staffId: 's1', at })

    expect(order.id).toMatch(/^[0-9a-f-]{36}$/)
    expect(order.created_at).toBe('2026-07-01T20:00:00.000Z')
    expect(order.status).toBe('confirmed')
    expect(order.items).toEqual([
      { product_id: 'p1', slug: 'jupiler', name: 'Jupiler', qty: 1, unit_price_coupons: 1 },
      { product_id: 'p2', slug: 'gin-tonic', name: 'Gin-Tonic', qty: 1, unit_price_coupons: 4 },
    ])
  })

  it('never puts device_id or total_coupons in the payload', () => {
    // The server derives both. OrderIn forbids extra fields, so sending them is a 422.
    const cart = useCart()
    cart.add(jupiler)
    const order = cart.buildOrder({ editionId: 'e1', barId: 'b1', staffId: 's1', at: new Date() })
    expect(order).not.toHaveProperty('device_id')
    expect(order).not.toHaveProperty('total_coupons')
  })

  it('gives each order a different id', () => {
    const cart = useCart()
    cart.add(jupiler)
    const ctx = { editionId: 'e1', barId: 'b1', staffId: 's1', at: new Date() }
    expect(cart.buildOrder(ctx).id).not.toBe(cart.buildOrder(ctx).id)
  })
})
