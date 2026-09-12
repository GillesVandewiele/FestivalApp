import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { OrderPayload } from '../api/client'
import type { Product } from './session'

export interface CartLine {
  product: Product
  qty: number
}

export interface OrderContext {
  editionId: string
  barId: string
  staffId: string
  at: Date
}

export const useCart = defineStore('cart', () => {
  const lines = ref<CartLine[]>([])

  const totalCoupons = computed(() =>
    lines.value.reduce((sum, l) => sum + l.qty * l.product.price_coupons, 0),
  )
  const isEmpty = computed(() => lines.value.length === 0)

  function add(product: Product): void {
    const line = lines.value.find((l) => l.product.id === product.id)
    if (line) line.qty += 1
    else lines.value.push({ product, qty: 1 })
  }

  function remove(productId: string): void {
    const index = lines.value.findIndex((l) => l.product.id === productId)
    if (index === -1) return
    const line = lines.value[index]
    if (line.qty > 1) line.qty -= 1
    else lines.value.splice(index, 1)
  }

  function clear(): void {
    lines.value = []
  }

  function qtyOf(productId: string): number {
    return lines.value.find((l) => l.product.id === productId)?.qty ?? 0
  }

  /**
   * The tablet mints the id. That single choice is what makes syncing idempotent:
   * the same order can be retried any number of times and upserts to one document.
   */
  function buildOrder(ctx: OrderContext): OrderPayload {
    return {
      id: crypto.randomUUID(),
      edition_id: ctx.editionId,
      bar_id: ctx.barId,
      staff_id: ctx.staffId,
      items: lines.value.map((l) => ({
        product_id: l.product.id,
        slug: l.product.slug,
        name: l.product.name, // snapshotted: a later rename must not rewrite history
        qty: l.qty,
        unit_price_coupons: l.product.price_coupons,
      })),
      created_at: ctx.at.toISOString(),
      status: 'confirmed',
    }
  }

  return { lines, totalCoupons, isEmpty, add, remove, clear, qtyOf, buildOrder }
})
