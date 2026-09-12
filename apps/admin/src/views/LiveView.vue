<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import EChart from '../charts/EChart.vue'
import {
  hourlyOption,
  hourlyStackedOption,
  type HourMetric,
  type HourRow,
  type HourStack,
} from '../charts/options'
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
const stack = ref<HourStack>({ hours: [], series: [] })
const staffDrinks = ref<{ drinks: number; value_eur: number } | null>(null)
const metric = ref<HourMetric>('qty')
// One split at a time: totaal, per drank, or the coarser per categorie.
const split = ref<'none' | 'product' | 'category'>('none')

const METRICS: [HourMetric, string][] = [
  ['qty', 'consumpties'],
  ['revenue_eur', 'omzet'],
  ['margin_eur', 'marge'],
]

const SPLITS: ['none' | 'product' | 'category', string][] = [
  ['none', 'totaal'],
  ['category', 'per categorie'],
  ['product', 'per drank'],
]

/** Drinks left out of a margin stack because their cost price is not filled in. A
 *  zero-height segment would read as "sold nothing", which is a different claim. */
const excluded = computed(() => stack.value.excluded ?? [])
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
    staffDrinks.value = await auth.client.stats('staff-consumption', { edition_id: id })
    stack.value = await auth.client.stats('by-hour-split', {
      edition_id: id,
      metric: metric.value,
      group_by: split.value === 'category' ? 'category' : 'product',
    })
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
// The split is computed per metric and per grouping, so either change needs a
// fresh one from the server.
watch([metric, split], refresh)
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
        v-if="staffDrinks && staffDrinks.drinks > 0"
        label="Personeel"
        :value="formatNumber(staffDrinks.drinks)"
        :note="`gratis, waarde ${formatEur(staffDrinks.value_eur)}`"
      />
      <StatTile
        label="Bestellingen"
        :value="formatNumber(overview?.orders)"
        :note="overview?.voided_orders ? `${overview.voided_orders} geannuleerd` : undefined"
      />
    </div>

    <section class="card">
      <div class="card-head">
        <h2>Verkoop per uur</h2>
        <div class="toggles">
          <button
            v-for="[key, label] in METRICS"
            :key="key"
            :class="{ on: metric === key }"
            @click="metric = key"
          >
            {{ label }}
          </button>
          <span class="divider" aria-hidden="true"></span>
          <button
            v-for="[key, label] in SPLITS"
            :key="key"
            :class="{ on: split === key }"
            @click="split = key"
          >
            {{ label }}
          </button>
        </div>
      </div>
      <EChart
        :option="
          split === 'none' ? hourlyOption(hours, metric) : hourlyStackedOption(stack, metric)
        "
        :height="280"
      />
      <p v-if="metric === 'margin_eur' && excluded.length" class="muted small">
        Zonder {{ excluded.join(', ') }}: daarvan is de inkoopprijs nog niet ingevuld, dus de
        marge is onbekend. Vul die aan bij Instellingen.
      </p>
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
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.card-head h2 {
  margin: 0;
}
.toggles {
  display: flex;
  gap: 6px;
  align-items: center;
}
.toggles button {
  min-height: 32px;
  padding: 0 12px;
  font-size: 14px;
}
.toggles .on {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  font-weight: 600;
}
.divider {
  width: 1px;
  align-self: stretch;
  margin: 0 4px;
  background: var(--line);
}
.small {
  font-size: 13px;
  margin-top: 8px;
}
</style>
