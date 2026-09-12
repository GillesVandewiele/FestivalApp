import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createClient } from '../api/client'
import { db } from '../db/schema'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export interface Product {
  id: string
  slug: string
  name: string
  category: string
  price_coupons: number
  sort_order: number
}

export interface Catalog {
  edition: { id: string; name: string }
  bar: { id: string; name: string }
  products: Product[]
  staff: { id: string; name: string }[]
}

export const useSession = defineStore('session', () => {
  const token = ref<string | null>(null)
  const catalog = ref<Catalog | null>(null)
  const staffId = ref<string | null>(null)
  const clockOffsetMs = ref(0)

  const client = createClient(API_BASE, () => token.value)

  /** Server-corrected time. A tablet with a wrong clock must not shift the hourly stats. */
  function now(): Date {
    return new Date(Date.now() + clockOffsetMs.value)
  }

  async function load(): Promise<void> {
    token.value = ((await db.meta.get('token'))?.value as string) ?? null
    catalog.value = ((await db.meta.get('catalog'))?.value as Catalog) ?? null
    staffId.value = ((await db.meta.get('staffId'))?.value as string) ?? null
    clockOffsetMs.value = ((await db.meta.get('clockOffsetMs'))?.value as number) ?? 0
  }

  async function enrol(newToken: string): Promise<void> {
    token.value = newToken
    await refresh() // fails loudly on a bad token, before anything is persisted
    await db.meta.put({ key: 'token', value: newToken })
  }

  /** Refresh the cached catalog and re-measure clock skew. */
  async function refresh(): Promise<void> {
    const data = (await client.getBootstrap()) as Catalog & { server_time: string }
    catalog.value = data
    clockOffsetMs.value = new Date(data.server_time).getTime() - Date.now()
    await db.meta.put({ key: 'catalog', value: JSON.parse(JSON.stringify(data)) })
    await db.meta.put({ key: 'clockOffsetMs', value: clockOffsetMs.value })
  }

  async function chooseStaff(id: string | null): Promise<void> {
    staffId.value = id
    await db.meta.put({ key: 'staffId', value: id })
  }

  return {
    token,
    catalog,
    staffId,
    clockOffsetMs,
    client,
    now,
    load,
    enrol,
    refresh,
    chooseStaff,
  }
})
