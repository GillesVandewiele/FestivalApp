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
  total_units: number | null
  surplus_units: number | null
  cost_eur: number | null
  cost_known: boolean
  had_stockout: boolean
  estimated_lost: number | null
  demand_base: number
  basis: 'sold' | 'measured' | 'buffer'
}

interface StockoutRow {
  slug: string
  name: string
  hours_out: number
  share_before_pct: number
  drinks_during_outage: number
  estimated_lost: number | null
  reliable: boolean
}

const auth = useAuth()
const editions = useEditions()

const products = ref<ProductRow[]>([])
const hours = ref<HourRow[]>([])
const peaks = ref<{ name: string; peak_hour: number; peak_qty: number }[]>([])
const comparison = ref<CompareRow[]>([])
const advice = ref<AdviceRow[]>([])
const stockouts = ref<StockoutRow[]>([])
const staffUse = ref<{
  drinks: number
  coupons: number
  value_eur: number
  per_product: { slug: string; name: string; qty: number; coupons: number }[]
  per_staff: { staff_id: string; name: string; drinks: number; value_eur: number }[]
  per_bar: { bar_id: string; name: string; drinks: number; value_eur: number }[]
} | null>(null)

const compareTo = ref<string | null>(null)
const growthPct = ref<number | null>(null)
const safetyPct = ref(10)

const missingCosts = computed(() => products.value.filter((p) => !p.cost_known))
const totalCost = computed(() =>
  advice.value.some((r) => r.cost_known)
    ? advice.value.reduce((s, r) => s + (r.cost_eur ?? 0), 0)
    : null,
)
const totalSurplus = computed(() =>
  advice.value.reduce((s, r) => s + (r.surplus_units ?? 0), 0),
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
  staffUse.value = await auth.client.stats('staff-consumption', { edition_id: id })
  stockouts.value = await auth.client.stats('stockout-impact', { edition_id: id })
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

    <section v-if="stockouts.length" class="card">
      <h2>Wat we misliepen toen iets op was</h2>
      <p class="muted small">
        Een drank die opraakt verkocht wat er stond, niet wat mensen wilden. De schatting
        is het aandeel dat die drank had vóór ze op was, toegepast op alles wat er nadien
        nog over de toog ging.
      </p>
      <table>
        <thead>
          <tr>
            <th>Drank</th><th>Uren op</th><th>Aandeel ervoor</th>
            <th>Verkocht in die uren</th><th>Gemist</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in stockouts" :key="r.slug">
            <td>{{ r.name }}</td>
            <td>{{ r.hours_out }}</td>
            <td>{{ formatPct(r.share_before_pct) }}</td>
            <td>{{ formatNumber(r.drinks_during_outage) }}</td>
            <td>
              <strong v-if="r.reliable">{{ formatNumber(r.estimated_lost) }}</strong>
              <span v-else class="muted" title="Te vroeg opgeraakt om betrouwbaar te schatten">
                te weinig gegevens
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section id="personeel" class="card">
      <h2>Wat het personeel dronk</h2>
      <p class="muted small">
        Deze consumpties zijn gratis en tellen nergens mee als omzet. Ze staan hier apart, zodat
        je weet wat ze gekost hebben.
      </p>
      <p v-if="!staffUse || staffUse.drinks === 0" class="muted">
        Nog niets geregistreerd. Medewerkers zetten de knop <strong>personeel</strong> aan in de
        bar-app voordat ze afrekenen; die consumpties zijn gratis en komen hier terecht.
      </p>
      <div v-if="staffUse && staffUse.drinks > 0" class="staff-totals">
        <span><strong>{{ formatNumber(staffUse.drinks) }}</strong> consumpties</span>
        <span><strong>{{ formatNumber(staffUse.coupons) }}</strong> bonnetjes</span>
        <span>waarde <strong>{{ formatEur(staffUse.value_eur) }}</strong></span>
      </div>
      <div v-if="staffUse && staffUse.drinks > 0" class="cols">
        <table>
          <thead><tr><th>Drank</th><th>Aantal</th></tr></thead>
          <tbody>
            <tr v-for="r in staffUse.per_product" :key="r.slug">
              <td>{{ r.name }}</td><td>{{ formatNumber(r.qty) }}</td>
            </tr>
          </tbody>
        </table>
        <table>
          <thead><tr><th>Medewerker</th><th>Aantal</th><th>Waarde</th></tr></thead>
          <tbody>
            <tr v-for="r in staffUse.per_staff" :key="r.staff_id">
              <td>{{ r.name }}</td>
              <td>{{ formatNumber(r.drinks) }}</td>
              <td>{{ formatEur(r.value_eur) }}</td>
            </tr>
          </tbody>
        </table>
        <table>
          <thead><tr><th>Verkooppunt</th><th>Aantal</th><th>Waarde</th></tr></thead>
          <tbody>
            <tr v-for="r in staffUse.per_bar" :key="r.bar_id">
              <td>{{ r.name }}</td>
              <td>{{ formatNumber(r.drinks) }}</td>
              <td>{{ formatEur(r.value_eur) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
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
            <th>Product</th><th>Verkocht</th><th>Groei</th><th>Veiligheid</th>
            <th>Advies</th><th>Verpakking</th><th>Te bestellen</th><th>Restant</th><th>Kost</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in advice" :key="r.slug">
            <td>
              {{ r.name }}
              <span
                v-if="r.had_stockout"
                class="flag"
                :title="
                  r.basis === 'measured'
                    ? 'Was op. De vraag is geschat uit het aandeel vóór het opraakte.'
                    : 'Was op, maar te vroeg om te schatten. Vandaar een ruimere marge.'
                "
              >
                was op
              </span>
            </td>
            <td>
              {{ formatNumber(r.sold) }}
              <span v-if="r.estimated_lost" class="muted sub">
                +{{ formatNumber(r.estimated_lost) }} gemist
              </span>
            </td>
            <td>{{ formatPct(r.growth_pct) }}</td>
            <td>{{ formatPct(r.safety_pct) }}</td>
            <td><strong>{{ formatNumber(r.advised) }}</strong></td>
            <td class="muted">{{ r.purchase_unit ? `${r.purchase_unit} van ${r.unit_size}` : '—' }}</td>
            <td>
              {{ formatNumber(r.units_to_order) }}
              <span v-if="r.total_units" class="muted sub">= {{ formatNumber(r.total_units) }}</span>
            </td>
            <td class="muted">{{ r.surplus_units === null ? '—' : `+${formatNumber(r.surplus_units)}` }}</td>
            <td :class="{ muted: !r.cost_known }">{{ formatEur(r.cost_eur) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colspan="7"><strong>Totaal</strong></td>
            <td class="muted">+{{ formatNumber(totalSurplus) }}</td>
            <td><strong>{{ formatEur(totalCost) }}</strong></td>
          </tr>
        </tfoot>
      </table>
      <p class="muted small">
        Advies = vraag × (1 + groei) × (1 + veiligheid), afgerond naar boven op hele
        verpakkingen. <strong>Restant</strong> is wat je daardoor te veel koopt: je kan geen halve
        bak bestellen en ook geen halve terugbrengen, dus dat blijft over. Producten die uitverkocht
        raakten tellen niet alleen wat verkocht is: waar er genoeg gegevens zijn, wordt geschat
        wat ze zouden verkocht hebben en telt dat mee als vraag. Lukt dat niet, dan krijgen ze
        25% veiligheid in plaats van {{ safetyPct }}%.
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
.sub {
  font-size: 12px;
  margin-left: 6px;
}
.staff-totals {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin: 12px 0 4px;
}
.staff-totals strong {
  font-size: 20px;
  font-variant-numeric: tabular-nums;
}
tfoot td {
  border-bottom: none;
}
</style>
