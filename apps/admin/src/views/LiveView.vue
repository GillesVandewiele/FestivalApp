<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import EChart from '../charts/EChart.vue'
import { hourlyOption, type HourRow } from '../charts/options'
import { formatEur, formatNumber } from '../charts/theme'
import StatTile from '../components/StatTile.vue'
import { useAuth } from '../stores/auth'
import { useEditions } from '../stores/editions'

const POLL_MS = 15000

const auth = useAuth()
const editions = useEditions()

const overview = ref<Record<string, number | null> | null>(null)
const products = ref<{ name: string; qty: number; coupons: number }[]>([])
const bars = ref<{ name: string; qty: number; coupons: number }[]>([])
const staff = ref<{ name: string; orders: number; qty: number; voided: number }[]>([])
const hours = ref<HourRow[]>([])
const updatedAt = ref('')
const failed = ref(false)

/** Margin only counts products whose cost price is entered, so say what it omits. */
const marginNote = computed(() => {
  const missing = overview.value?.cost_missing ?? 0
  if (missing === 0) return undefined
  return `zonder ${missing} product${missing === 1 ? '' : 'en'} zonder inkoopprijs`
})

let timer: ReturnType<typeof setInterval> | undefined

async function refresh() {
  const id = editions.currentId
  if (!id) return
  try {
    const [o, p, b, s, h] = await Promise.all([
      auth.client.stats('overview', { edition_id: id }),
      auth.client.stats('by-product', { edition_id: id }),
      auth.client.stats('by-bar', { edition_id: id }),
      auth.client.stats('by-staff', { edition_id: id }),
      auth.client.stats('by-hour', { edition_id: id }),
    ])
    overview.value = o
    products.value = p
    bars.value = b
    staff.value = s
    hours.value = h
    updatedAt.value = new Date().toLocaleTimeString('nl-BE')
    failed.value = false
  } catch {
    // Keep showing the last good numbers rather than blanking the screen. A
    // sleeping backend is not a reason to hide the figures already on it.
    failed.value = true
  }
}

onMounted(async () => {
  await editions.load()
  await refresh()
  timer = setInterval(refresh, POLL_MS)
})
onBeforeUnmount(() => timer && clearInterval(timer))
watch(() => editions.currentId, refresh)
</script>

<template>
  <div>
    <header class="head">
      <div>
        <h1>Live</h1>
        <p class="muted">
          <template v-if="failed">Verbinding kwijt. Cijfers van {{ updatedAt }}.</template>
          <template v-else-if="updatedAt">Bijgewerkt om {{ updatedAt }}, ververst elke 15 s.</template>
        </p>
      </div>
      <select v-model="editions.currentId">
        <option v-for="e in editions.all" :key="e.id" :value="e.id">{{ e.name }}</option>
      </select>
    </header>

    <div class="tiles">
      <StatTile label="Consumpties" :value="formatNumber(overview?.drinks)" />
      <StatTile label="Bonnetjes" :value="formatNumber(overview?.coupons)" />
      <StatTile label="Omzet" :value="formatEur(overview?.revenue_eur)" />
      <StatTile
        label="Marge"
        :value="formatEur(overview?.margin_eur)"
        :note="marginNote"
      />
      <StatTile
        label="Bestellingen"
        :value="formatNumber(overview?.orders)"
        :note="overview?.voided_orders ? `${overview.voided_orders} geannuleerd` : undefined"
      />
    </div>

    <section class="card">
      <h2>Verkoop per uur</h2>
      <EChart :option="hourlyOption(hours)" :height="260" />
    </section>

    <div class="cols">
      <section class="card">
        <h2>Per drank</h2>
        <table>
          <thead><tr><th>Drank</th><th>Aantal</th><th>Bonnetjes</th></tr></thead>
          <tbody>
            <tr v-for="p in products" :key="p.name">
              <td>{{ p.name }}</td><td>{{ formatNumber(p.qty) }}</td><td>{{ formatNumber(p.coupons) }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="card">
        <h2>Per verkooppunt</h2>
        <table>
          <thead><tr><th>Bar</th><th>Aantal</th><th>Bonnetjes</th></tr></thead>
          <tbody>
            <tr v-for="b in bars" :key="b.name">
              <td>{{ b.name }}</td><td>{{ formatNumber(b.qty) }}</td><td>{{ formatNumber(b.coupons) }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="card">
        <h2>Per medewerker</h2>
        <table>
          <thead><tr><th>Naam</th><th>Bestellingen</th><th>Aantal</th><th>Geannuleerd</th></tr></thead>
          <tbody>
            <tr v-for="s in staff" :key="s.name">
              <td>{{ s.name }}</td><td>{{ formatNumber(s.orders) }}</td>
              <td>{{ formatNumber(s.qty) }}</td><td>{{ formatNumber(s.voided) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </div>
</template>

<style scoped>
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.cols {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 18px;
}
.cols .card {
  margin-bottom: 0;
}
</style>
