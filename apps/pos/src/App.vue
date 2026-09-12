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
  })

  await enqueue(order) // durable before the screen clears
  lastOrderId.value = order.id
  cart.clear()
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
      <button class="staff" @click="switchStaff">{{ staffName }}</button>
      <SyncBadge :online="queue.online" :pending="queue.pendingCount" />
    </header>

    <ProductGrid
      :products="session.catalog.products"
      :qty-of="cart.qtyOf"
      :sold-out="soldOut"
      @add="cart.add"
      @remove="(p) => cart.remove(p.id)"
    />

    <OrderStrip :lines="cart.lines" @remove="cart.remove" @clear="cart.clear" />

    <TotalBar
      :total="cart.totalCoupons"
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
.staff {
  margin-left: auto;
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
