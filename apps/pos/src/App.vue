<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EnrolScreen from './components/EnrolScreen.vue'
import OrderStrip from './components/OrderStrip.vue'
import ProductGrid from './components/ProductGrid.vue'
import StaffPicker from './components/StaffPicker.vue'
import SyncBadge from './components/SyncBadge.vue'
import TotalBar from './components/TotalBar.vue'
import { enqueue, voidQueued } from './db/outbox'
import { useCart } from './stores/cart'
import { useQueue } from './stores/queue'
import { useSession, type Product } from './stores/session'

const session = useSession()
const cart = useCart()
const queue = useQueue()

const soldOut = ref(new Set<string>())
const lastOrderId = ref<string | null>(null)
const enrolError = ref('')

/**
 * Staff drinks are free but still counted. Deliberately a quiet toggle in the header
 * rather than a button by the drinks: it is used a few times a night, not every round.
 * It resets after every commit so it cannot be left on by accident, which would book
 * a paying customer's round as free.
 */
const staffMode = ref(false)

const staffName = computed(
  () => session.catalog?.staff.find((s) => s.id === session.staffId)?.name ?? '',
)

onMounted(async () => {
  await session.load()
  if (session.token) {
    try {
      await session.refresh()
    } catch {
      // Offline at startup is expected. The cached catalog is already loaded,
      // which is the whole point of caching it.
    }
    queue.start()
    await queue.refreshCount()
  }
  void requestWakeLock()
})

async function requestWakeLock() {
  try {
    const nav = navigator as Navigator & {
      wakeLock?: { request: (type: 'screen') => Promise<unknown> }
    }
    await nav.wakeLock?.request('screen')
  } catch {
    // Unsupported or denied. Not worth interrupting staff over.
  }
}

async function onEnrol(token: string) {
  enrolError.value = ''
  try {
    await session.enrol(token)
    queue.start()
  } catch {
    session.token = null
    enrolError.value = 'Koppelen mislukt. Controleer de code en de verbinding.'
  }
}

async function commit() {
  const catalog = session.catalog
  if (!catalog || !session.staffId) return

  const order = cart.buildOrder({
    editionId: catalog.edition.id,
    barId: catalog.bar.id,
    staffId: session.staffId,
    at: session.now(),
    kind: staffMode.value ? 'staff' : 'sale',
  })

  await enqueue(order) // durable before the screen clears
  lastOrderId.value = order.id
  cart.clear()
  staffMode.value = false // never sticky
  await queue.refreshCount()
  void queue.drain() // fire and forget: the UI never waits on the network
}

async function undo() {
  if (!lastOrderId.value || !session.staffId) return
  await voidQueued(lastOrderId.value, { type: 'staff', id: session.staffId })
  lastOrderId.value = null
  await queue.refreshCount()
  void queue.drain()
}

function switchStaff() {
  void session.chooseStaff(null)
}
</script>

<template>
  <EnrolScreen v-if="!session.token" :error="enrolError" @enrol="onEnrol" />

  <StaffPicker
    v-else-if="!session.staffId && session.catalog"
    :staff="session.catalog.staff"
    :bar-name="session.catalog.bar.name"
    @choose="session.chooseStaff"
  />

  <div v-else-if="session.catalog" class="app">
    <header>
      <span class="bar-name">{{ session.catalog.bar.name }}</span>
      <button
        class="mode"
        :class="{ on: staffMode }"
        :aria-pressed="staffMode"
        @click="staffMode = !staffMode"
      >
        personeel
      </button>
      <button class="staff" @click="switchStaff">{{ staffName }}</button>
      <SyncBadge :online="queue.online" :pending="queue.pendingCount" />
    </header>

    <ProductGrid
      :products="session.catalog.products"
      :categories="session.catalog.categories ?? []"
      :qty-of="cart.qtyOf"
      :sold-out="soldOut"
      @add="cart.add"
      @remove="(p) => cart.remove(p.id)"
    />

    <OrderStrip :lines="cart.lines" @remove="cart.remove" @clear="cart.clear" />

    <TotalBar
      :total="cart.totalCoupons"
      :staff-mode="staffMode"
      :can-undo="lastOrderId !== null"
      @commit="commit"
      @undo="undo"
    />
  </div>

  <p v-else class="loading">Laden…</p>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
}
header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px var(--gap);
  border-bottom: 1px solid var(--line);
}
.bar-name {
  font-weight: 800;
  font-size: 18px;
}
.mode {
  margin-left: auto;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: transparent;
  color: var(--text-dim);
  font: inherit;
  font-size: 14px;
  cursor: pointer;
}
.mode.on {
  border-color: var(--staff);
  background: color-mix(in srgb, var(--staff) 20%, transparent);
  color: var(--staff);
  font-weight: 700;
}
.staff {
  min-height: 42px;
  padding: 0 18px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 16px;
}
.staff:active {
  background: var(--surface-press);
}
.loading {
  padding: 24px;
  color: var(--text-dim);
}
</style>
