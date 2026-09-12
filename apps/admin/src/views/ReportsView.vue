<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import EChart from '../charts/EChart.vue'
import {
  compareOption,
  hourlyOption,
  marginVolumeOption,
  paretoOption,
  type CompareRow,
  type HourRow,
  type ProductRow,
} from '../charts/options'
import { formatEur, formatNumber, formatPct } from '../charts/theme'
import { useAuth } from '../stores/auth'
import { useEditions } from '../stores/editions'

interface AdviceRow {
  slug: string
  name: string
  sold: number
  growth_pct: number
  safety_pct: number
  advised: number
  purchase_unit: string | null
  unit_size: number | null
  units_to_order: number | null
  cost_eur: number | null
  cost_known: boolean
  had_stockout: boolean
}

const auth = useAuth()
const editions = useEditions()

const products = ref<ProductRow[]>([])
const hours = ref<HourRow[]>([])
const peaks = ref<{ name: string; peak_hour: number; peak_qty: number }[]>([])
const comparison = ref<CompareRow[]>([])
const advice = ref<AdviceRow[]>([])

const compareTo = ref<string | null>(null)
const growthPct = ref<number | null>(null)
const safetyPct = ref(10)

const missingCosts = computed(() => products.value.filter((p) => !p.cost_known))
const totalCost = computed(() =>
  advice.value.some((r) => r.cost_known)
    ? advice.value.reduce((s, r) => s + (r.cost_eur ?? 0), 0)
    : null,
)
const editionName = computed(() => editions.byId(editions.currentId)?.name ?? '')
const compareName = computed(() => editions.byId(compareTo.value)?.name ?? '')

async function load() {
  const id = editions.currentId
  if (!id) return
  const [p, h, k] = await Promise.all([
    auth.client.stats('by-product', { edition_id: id }),
    auth.client.stats('by-hour', { edition_id: id }),
    auth.client.stats('peak-per-bar', { edition_id: id }),
  ])
  products.value = p
  hours.value = h
  peaks.value = k
  await Promise.all([loadCompare(), loadAdvice()])
}

async function loadCompare() {
  if (!editions.currentId || !compareTo.value) {
    comparison.value = []
    return
  }
  comparison.value = await auth.client.stats('compare', {
    edition_a: compareTo.value,
    edition_b: editions.currentId,
  })
}

async function loadAdvice() {
  if (!editions.currentId) return
  advice.value = await auth.client.stats('procurement', {
    edition_id: editions.currentId,
    safety_pct: safetyPct.value,
    growth_pct: growthPct.value ?? undefined,
    compare_to: compareTo.value ?? undefined,
  })
}

onMounted(async () => {
  await editions.load()
  const others = editions.all.filter((e) => e.id !== editions.currentId)
  compareTo.value = others[0]?.id ?? null
  await load()
})
watch(() => editions.currentId, load)
watch(compareTo, async () => {
  await loadCompare()
  await loadAdvice()
})
</script>

<template>
  <div>
    <header class="head">
      <div>
        <h1>Rapporten</h1>
        <p class="muted">Wat verkocht er, wat leverde het op, en wat moet je volgend jaar kopen.</p>
      </div>
      <select v-model="editions.currentId">
        <option v-for="e in editions.all" :key="e.id" :value="e.id">{{ e.name }}</option>
      </select>
    </header>

    <p v-if="missingCosts.length" class="notice">
      Van {{ missingCosts.length }} product{{ missingCosts.length === 1 ? '' : 'en' }} ontbreekt de
      inkoopprijs, dus marge en inkoopkost blijven daar leeg. Vul ze aan bij Instellingen zodra de
      facturen binnen zijn.
    </p>

    <section class="card">
      <div class="card-head">
        <h2>Winst per product</h2>
        <a :href="auth.client.csvUrl('by-product', editions.currentId ?? '')">CSV</a>
      </div>
      <table>
        <thead>
          <tr>
            <th>Product</th><th>Aantal</th><th>Bonnetjes</th><th>Omzet</th>
            <th>Inkoop</th><th>Marge</th><th>Marge %</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in products" :key="p.slug">
            <td>{{ p.name }}</td>
            <td>{{ formatNumber(p.qty) }}</td>
            <td>{{ formatNumber((p as never as { coupons: number }).coupons) }}</td>
            <td>{{ formatEur(p.revenue_eur) }}</td>
            <td :class="{ muted: !p.cost_known }">
              {{ formatEur((p as never as { cost_eur: number | null }).cost_eur) }}
            </td>
            <td :class="{ muted: !p.cost_known }">{{ formatEur(p.margin_eur) }}</td>
            <td :class="{ muted: !p.cost_known }">
              {{ formatPct((p as never as { margin_pct: number | null }).margin_pct) }}
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <div class="cols">
      <section class="card">
        <h2>Marge tegenover volume</h2>
        <p class="muted small">
          Rechtsboven verkoopt veel met goede marge. Linksonder is een kandidaat om te schrappen.
          De bol is de totale winst.
        </p>
        <EChart :option="marginVolumeOption(products)" :height="300" />
      </section>

      <section class="card">
        <h2>Welke producten dragen het volume</h2>
        <p class="muted small">
          De lijn is het cumulatieve aandeel. Waar die 80% raakt, staan de producten waarover het
          loont te onderhandelen.
        </p>
        <EChart :option="paretoOption(products)" :height="300" />
      </section>
    </div>

    <section class="card">
      <div class="card-head">
        <h2>Verkoop per uur</h2>
        <a :href="auth.client.csvUrl('by-hour', editions.currentId ?? '')">CSV</a>
      </div>
      <EChart :option="hourlyOption(hours)" :height="260" />
      <table>
        <thead><tr><th>Verkooppunt</th><th>Drukste uur</th><th>Consumpties in dat uur</th></tr></thead>
        <tbody>
          <tr v-for="b in peaks" :key="b.name">
            <td>{{ b.name }}</td>
            <td>{{ String(b.peak_hour).padStart(2, '0') }}u</td>
            <td>{{ formatNumber(b.peak_qty) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="muted small">
        Het drukste uur per bar bepaalt hoeveel koeling en voorraad daar moet staan, beter dan het
        dagtotaal dat doet.
      </p>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Vergelijking met een vorige editie</h2>
        <select v-model="compareTo">
          <option :value="null">Geen vergelijking</option>
          <option v-for="e in editions.all.filter((x) => x.id !== editions.currentId)" :key="e.id" :value="e.id">
            {{ e.name }}
          </option>
        </select>
      </div>
      <template v-if="comparison.length">
        <EChart :option="compareOption(comparison, compareName, editionName)" :height="300" />
        <table>
          <thead>
            <tr><th>Product</th><th>{{ compareName }}</th><th>{{ editionName }}</th><th>Verschil</th><th>Groei</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in comparison" :key="r.slug">
              <td>{{ r.name }}</td>
              <td>{{ formatNumber(r.qty_a) }}</td>
              <td>{{ formatNumber(r.qty_b) }}</td>
              <td>{{ r.qty_b - r.qty_a > 0 ? '+' : '' }}{{ formatNumber(r.qty_b - r.qty_a) }}</td>
              <td>{{ formatPct((r as never as { pct: number | null }).pct) }}</td>
            </tr>
          </tbody>
        </table>
      </template>
      <p v-else class="muted">
        Kies een editie om mee te vergelijken. Na de tweede editie wordt dit vanzelf bruikbaar.
      </p>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Inkoopadvies voor volgend jaar</h2>
        <a :href="auth.client.csvUrl('procurement', editions.currentId ?? '')">CSV</a>
      </div>
      <div class="controls">
        <label>Verwachte groei
          <input v-model.number="growthPct" type="number" step="5" placeholder="uit vergelijking" @change="loadAdvice" />
        </label>
        <label>Veiligheidsmarge %
          <input v-model.number="safetyPct" type="number" step="5" @change="loadAdvice" />
        </label>
      </div>
      <table>
        <thead>
          <tr>
            <th>Product</th><th>Verkocht</th><th>Groei</th><th>Marge</th>
            <th>Advies</th><th>Eenheid</th><th>Bestellen</th><th>Kost</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in advice" :key="r.slug">
            <td>
              {{ r.name }}
              <span v-if="r.had_stockout" class="flag" title="Dit product was uitverkocht, dus de verkoop onderschat de vraag">
                was op
              </span>
            </td>
            <td>{{ formatNumber(r.sold) }}</td>
            <td>{{ formatPct(r.growth_pct) }}</td>
            <td>{{ formatPct(r.safety_pct) }}</td>
            <td><strong>{{ formatNumber(r.advised) }}</strong></td>
            <td class="muted">{{ r.purchase_unit ? `${r.purchase_unit} van ${r.unit_size}` : '—' }}</td>
            <td>{{ formatNumber(r.units_to_order) }}</td>
            <td :class="{ muted: !r.cost_known }">{{ formatEur(r.cost_eur) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr><td colspan="7"><strong>Totaal</strong></td><td><strong>{{ formatEur(totalCost) }}</strong></td></tr>
        </tfoot>
      </table>
      <p class="muted small">
        Advies = verkocht × (1 + groei) × (1 + veiligheidsmarge), afgerond naar boven op hele
        eenheden. Producten die uitverkocht raakten krijgen automatisch 25% marge in plaats van
        {{ safetyPct }}%: die verkochten wat er stond, niet wat mensen wilden.
      </p>
    </section>
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
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.card-head h2 {
  margin: 0;
}
.cols {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 18px;
}
.cols .card {
  margin-bottom: 18px;
}
.controls {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.controls label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-dim);
}
.controls input {
  width: 170px;
}
.notice {
  padding: 10px 14px;
  border: 1px solid var(--warn);
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--warn) 10%, transparent);
  margin-bottom: 18px;
}
.flag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--warn) 22%, transparent);
  color: var(--ink);
  font-size: 12px;
}
.small {
  font-size: 13px;
}
tfoot td {
  border-bottom: none;
}
</style>
