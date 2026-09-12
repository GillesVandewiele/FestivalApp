import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import { ApiError, type SyncResult } from '../api/client'
import { markSynced, pending, pendingCount } from '../db/outbox'
import { markStockoutsSynced, pendingStockouts } from '../db/stockouts'
import { useSession } from './session'

const DRAIN_INTERVAL_MS = 5000
const THROTTLED_BACKOFF_MS = 60_000

interface Syncer {
  syncOrders: (orders: never[]) => Promise<SyncResult>
  syncStockouts?: (stockouts: never[]) => Promise<{ accepted: string[] }>
}

export const useQueue = defineStore('queue', () => {
  const count = ref(0)
  const online = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
  const syncing = ref(false)
  /** The code this tablet holds is no longer valid. Retrying cannot fix it. */
  const unlinked = ref(false)
  /** The server is refusing this address for a while. */
  const throttledUntil = ref(0)
  const session = useSession()

  // shallowRef so tests can swap in a fake without touching the network.
  const client = shallowRef<Syncer>(session.client as unknown as Syncer)
  let timer: ReturnType<typeof setInterval> | undefined

  async function refreshCount(): Promise<void> {
    count.value = await pendingCount()
  }

  async function drainStockouts(): Promise<void> {
    const batch = await pendingStockouts()
    if (!batch.length || !client.value.syncStockouts) return
    const result = await client.value.syncStockouts(batch as never[])
    if (result.accepted?.length) await markStockoutsSynced(result.accepted)
  }

  async function drain(): Promise<void> {
    if (syncing.value) return // one drain at a time; a second would resend the same rows
    // Retrying a code the server has rejected cannot succeed, and hammering it gets
    // the whole venue's address throttled. Both of these stop the loop dead.
    if (unlinked.value) return
    if (Date.now() < throttledUntil.value) return

    syncing.value = true
    try {
      const batch = await pending()
      if (batch.length === 0) {
        // Stockouts still need sending even when no sale is waiting.
        await drainStockouts()
        online.value = true
        return
      }
      const result = await client.value.syncOrders(batch as never[])
      if (result.accepted?.length) await markSynced(result.accepted)
      await drainStockouts()
      online.value = true
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0
      if (status === 401 || status === 403) {
        // Not a network problem. Telling staff "offline" sends them to check the
        // wifi when the fix is to link the tablet again.
        unlinked.value = true
        stop()
      } else if (status === 429) {
        throttledUntil.value = Date.now() + THROTTLED_BACKOFF_MS
      } else {
        online.value = false // genuinely offline; stay queued and retry
      }
    } finally {
      syncing.value = false
      await refreshCount()
    }
  }

  function start(): Promise<void> {
    window.addEventListener('online', drain)
    timer = setInterval(drain, DRAIN_INTERVAL_MS)
    // Returned rather than fired and forgotten, so a caller that needs the first
    // drain to have finished can wait for it.
    return drain()
  }

  function stop(): void {
    window.removeEventListener('online', drain)
    if (timer) clearInterval(timer)
  }

  /** Re-linking keeps the queue: orders are keyed by an id this tablet already
   *  generated, so the new device syncs them without duplicating anything. */
  function relinked(): Promise<void> {
    unlinked.value = false
    throttledUntil.value = 0
    return start()
  }

  return {
    pendingCount: count,
    online,
    syncing,
    unlinked,
    throttledUntil,
    client,
    drain,
    start,
    stop,
    refreshCount,
    relinked,
  }
})
