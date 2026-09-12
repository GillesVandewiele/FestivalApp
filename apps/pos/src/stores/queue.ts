import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import type { SyncResult } from '../api/client'
import { markSynced, pending, pendingCount } from '../db/outbox'
import { useSession } from './session'

const DRAIN_INTERVAL_MS = 5000

interface Syncer {
  syncOrders: (orders: never[]) => Promise<SyncResult>
}

export const useQueue = defineStore('queue', () => {
  const count = ref(0)
  const online = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
  const syncing = ref(false)
  const session = useSession()

  // shallowRef so tests can swap in a fake without touching the network.
  const client = shallowRef<Syncer>(session.client as unknown as Syncer)
  let timer: ReturnType<typeof setInterval> | undefined

  async function refreshCount(): Promise<void> {
    count.value = await pendingCount()
  }

  async function drain(): Promise<void> {
    if (syncing.value) return // one drain at a time; a second would resend the same rows
    syncing.value = true
    try {
      const batch = await pending()
      if (batch.length === 0) {
        return
      }
      const result = await client.value.syncOrders(batch as never[])
      if (result.accepted?.length) await markSynced(result.accepted)
      online.value = true
    } catch {
      online.value = false // stay queued; the next tick retries
    } finally {
      syncing.value = false
      await refreshCount()
    }
  }

  function start(): void {
    window.addEventListener('online', drain)
    timer = setInterval(drain, DRAIN_INTERVAL_MS)
    void drain()
  }

  function stop(): void {
    window.removeEventListener('online', drain)
    if (timer) clearInterval(timer)
  }

  return { pendingCount: count, online, syncing, client, drain, start, stop, refreshCount }
})
