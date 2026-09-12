<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EnrolScreen from './components/EnrolScreen.vue'
import OrderStrip from './components/OrderStrip.vue'
import ProductGrid from './components/ProductGrid.vue'
import StaffPicker from './components/StaffPicker.vue'
import SyncBadge from './components/SyncBadge.vue'
import TotalBar from './components/TotalBar.vue'
import { enqueue, voidQueued } from './db/outbox'
import { soldOutIds, toggle as toggleStockout } from './db/stockouts'
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

/**
 * Stock mode. Marking a drink sold out is deliberately behind an explicit mode
 * rather than a gesture on the button: a mis-tap that locks a product out for the
 * night is a much worse failure than one extra tap. Inside the mode the same tap
 * puts it back, so nothing is one-way.
 */
const stockMode = ref(false)

const staffName = computed(
  () => session.catalog?.staff.find((s) => s.id === session.staffId)?.name ?? '',
)

onMounted(async () => {
  await session.load()
  soldOut.value = await soldOutIds()
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
    await queue.relinked() // clears the unlinked state and drains what was waiting
  } catch (e) {
    session.token = null
    enrolError.value =
      (e as { status?: number }).status === 401
        ? 'Deze code werkt niet. Vraag een nieuwe in de beheerdersapp.'
        : 'Koppelen mislukt. Controleer de verbinding.'
  }
}

async function unlink() {
  queue.stop()
  await session.unlink()
}

async function onProductTap(p: Product) {
  if (!stockMode.value) {
    cart.add(p)
    return
  }
  await toggleStockout(p.id, session.now())
  soldOut.value = await soldOutIds()
  void queue.drain() // stock changes reach the organiser as soon as there is signal
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
  <EnrolScreen
    v-if="!session.token"
    :error="enrolError"
    :queued="queue.pendingCount"
    @enrol="onEnrol"
  />

  <StaffPicker
    v-else-if="!session.staffId && session.catalog"
    :staff="session.catalog.staff"
    :bar-name="session.catalog.bar.name"
    @choose="session.chooseStaff"
    @unlink="unlink"
  />

  <div v-else-if="session.catalog" class="app">
    <!--
      An expired code is not a network problem. Saying "offline" sends staff to check
      the wifi when the fix is to enter a new code.
    -->
    <div v-if="queue.unlinked" class="alert">
      <span>
        Deze tablet is niet meer gekoppeld. Verkopen blijven bewaard, maar worden pas
        verstuurd na een nieuwe code.
      </span>
      <button @click="unlink">Nieuwe code invoeren</button>
    </div>
    <header>
      <span class="bar-name">{{ session.catalog.bar.name }}</span>
      <button
        class="mode"
        :class="{ on: staffMode }"
        :aria-pressed="staffMode"
        :disabled="stockMode"
        @click="staffMode = !staffMode"
      >
        personeel
      </button>
      <button
        class="mode stock"
        :class="{ on: stockMode }"
        :aria-pressed="stockMode"
        @click="stockMode = !stockMode"
      >
        voorraad<span v-if="soldOut.size" class="count">{{ soldOut.size }}</span>
      </button>
      <button class="staff" @click="switchStaff">{{ staffName }}</button>
      <SyncBadge :online="queue.online" :pending="queue.pendingCount" />
    </header>

    <div v-if="stockMode" class="stockbar">
      Tik een drank aan om ze op <em>op</em> te zetten, of terug in voorraad. Niets gaat
      verloren: nog eens tikken zet het meteen terug.
      <button @click="stockMode = false">Klaar</button>
    </div>

    <ProductGrid
      :products="session.catalog.products"
      :categories="session.catalog.categories ?? []"
      :qty-of="cart.qtyOf"
      :sold-out="soldOut"
      :stock-mode="stockMode"
      @add="onProductTap"
      @remove="(p) => cart.remove(p.id)"
    />

    <OrderStrip
      v-if="!stockMode"
      :lines="cart.lines"
      @remove="cart.remove"
      @clear="cart.clear"
    />

    <TotalBar
      v-if="!stockMode"
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
  gap: 10px;
  padding: 10px var(--gap);
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap; /* a narrow screen wraps rather than pushing the page sideways */
}
.bar-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
.mode:disabled {
  opacity: 0.35;
}
.mode.stock.on {
  border-color: var(--queued);
  background: color-mix(in srgb, var(--queued) 20%, transparent);
  color: var(--queued);
}
.count {
  margin-left: 7px;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--queued);
  color: #17130f;
  font-size: 12px;
  font-weight: 800;
}
.stockbar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px var(--gap);
  background: color-mix(in srgb, var(--queued) 16%, var(--bg));
  border-bottom: 1px solid var(--queued);
  font-size: 15px;
}
.stockbar em {
  color: var(--undo);
  font-style: normal;
  font-weight: 700;
}
.stockbar button {
  margin-left: auto;
  min-height: 38px;
  padding: 0 16px;
  border: 1px solid var(--text);
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-weight: 700;
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
.alert {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px var(--gap);
  background: color-mix(in srgb, var(--undo) 22%, var(--bg));
  border-bottom: 1px solid var(--undo);
  font-size: 15px;
}
.alert button {
  margin-left: auto;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid var(--text);
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-weight: 700;
  white-space: nowrap;
}
.loading {
  padding: 24px;
  color: var(--text-dim);
}
</style>
