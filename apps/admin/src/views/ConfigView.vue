<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAuth } from '../stores/auth'
import { useEditions } from '../stores/editions'

type Row = Record<string, unknown> & { id: string }

const auth = useAuth()
const editions = useEditions()

const tab = ref<'editions' | 'bars' | 'products' | 'staff' | 'devices'>('products')
const rows = ref<Row[]>([])
const barsForEdition = ref<Row[]>([])
const draft = ref<Record<string, unknown>>({})
const error = ref('')
const newToken = ref<{ label: string; token: string } | null>(null)

const TABS = [
  ['products', 'Dranken'],
  ['bars', 'Verkooppunten'],
  ['staff', 'Medewerkers'],
  ['editions', 'Edities'],
  ['devices', 'Tablets'],
] as const

const editionId = computed(() => editions.currentId)

function blankDraft() {
  const eid = editionId.value ?? ''
  if (tab.value === 'products')
    return { edition_id: eid, slug: '', name: '', category: 'bier', price_coupons: 1,
             cost_price_eur: null, purchase_unit: null, available_at: [] }
  if (tab.value === 'bars') return { edition_id: eid, name: '', sort_order: 0 }
  if (tab.value === 'staff') return { edition_id: eid, name: '' }
  if (tab.value === 'devices') return { edition_id: eid, bar_id: '', label: '' }
  return { name: '', year: new Date().getFullYear(), coupon_value_eur: 2.5,
           starts_at: new Date().toISOString(), ends_at: new Date().toISOString() }
}

async function load() {
  error.value = ''
  if (tab.value === 'devices') {
    // Ingetrokken toestellen verdwijnen uit de lijst: ze bestaan nog in de database
    // zodat oude verkopen toegewezen blijven, maar ze zijn geen keuze meer.
    rows.value = ((await auth.client.listDevices()) as Row[]).filter((d) => !d.revoked_at)
  } else {
    const scoped = tab.value === 'editions' ? undefined : (editionId.value ?? undefined)
    rows.value = (await auth.client.list(tab.value, scoped)) as Row[]
  }
  if (editionId.value) {
    barsForEdition.value = (await auth.client.list('bars', editionId.value)) as Row[]
  }
  draft.value = blankDraft()
}

async function create() {
  error.value = ''
  try {
    if (tab.value === 'devices') {
      const d = (await auth.client.enrollDevice(draft.value as never)) as {
        label: string
        token: string
      }
      // Shown once. There is no way to retrieve it later, by design.
      newToken.value = { label: d.label, token: d.token }
    } else {
      await auth.client.create(tab.value, draft.value)
    }
    await load()
  } catch (e) {
    error.value =
      (e as { status?: number }).status === 409
        ? 'Er bestaat al een product met deze slug in deze editie.'
        : 'Opslaan mislukt. Controleer de velden.'
  }
}

async function patch(row: Row, field: string, value: unknown) {
  await auth.client.update(tab.value, row.id, { [field]: value })
  await load()
}

async function rotate(row: Row) {
  const d = (await auth.client.rotateDevice(row.id)) as { label: string; token: string }
  // Shown once, same as a fresh enrolment. The previous code stopped working
  // the moment this call returned.
  newToken.value = { label: d.label, token: d.token }
  await load()
}

async function remove(row: Row) {
  if (tab.value === 'devices') {
    await auth.client.revokeDevice(row.id)
  } else {
    await auth.client.remove(tab.value, row.id)
  }
  await load()
}

function toggleBar(row: Row, barId: string) {
  const current = (row.available_at as string[]) ?? []
  const next = current.includes(barId)
    ? current.filter((b) => b !== barId)
    : [...current, barId]
  return patch(row, 'available_at', next)
}

onMounted(async () => {
  await editions.load()
  await load()
})
watch([tab, editionId], load)
</script>

<template>
  <div>
    <header class="head">
      <div>
        <h1>Instellingen</h1>
        <p class="muted">Wijzigingen bereiken de tablets bij hun volgende synchronisatie.</p>
      </div>
      <select v-if="tab !== 'editions'" v-model="editions.currentId">
        <option v-for="e in editions.all" :key="e.id" :value="e.id">{{ e.name }}</option>
      </select>
    </header>

    <nav class="tabs">
      <button v-for="[key, label] in TABS" :key="key" :class="{ on: tab === key }" @click="tab = key">
        {{ label }}
      </button>
    </nav>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="newToken" class="token card">
      <h2>Apparaatcode voor {{ newToken.label }}</h2>
      <p class="muted">
        Deze code is maar één keer zichtbaar. Plak hem nu in de bar-app. Een eerdere code van
        dit toestel werkt niet meer.
      </p>
      <code>{{ newToken.token }}</code>
      <button @click="newToken = null">Sluiten</button>
    </div>

    <section class="card">
      <h2>Toevoegen</h2>
      <div class="form">
        <template v-if="tab === 'products'">
          <label>Naam<input v-model="draft.name" /></label>
          <label>Slug<input v-model="draft.slug" placeholder="witte-wijn" /></label>
          <label>Categorie
            <select v-model="draft.category">
              <option>bier</option><option>wijn</option><option>cocktail</option>
              <option>fris</option><option>warm</option>
            </select>
          </label>
          <label>Bonnetjes<input v-model.number="draft.price_coupons" type="number" min="0" /></label>
          <label>Inkoopprijs €<input v-model.number="draft.cost_price_eur" type="number" step="0.01" /></label>
        </template>
        <template v-else-if="tab === 'devices'">
          <label>Label<input v-model="draft.label" placeholder="Tablet bar 1" /></label>
          <label>Verkooppunt
            <select v-model="draft.bar_id">
              <option v-for="b in barsForEdition" :key="b.id" :value="b.id">{{ b.name }}</option>
            </select>
          </label>
        </template>
        <template v-else-if="tab === 'editions'">
          <label>Naam<input v-model="draft.name" /></label>
          <label>Jaar<input v-model.number="draft.year" type="number" /></label>
          <label>Waarde bonnetje €<input v-model.number="draft.coupon_value_eur" type="number" step="0.1" /></label>
        </template>
        <template v-else>
          <label>Naam<input v-model="draft.name" /></label>
        </template>
        <button class="primary" @click="create">Toevoegen</button>
      </div>
      <p v-if="tab === 'products'" class="muted small">
        De slug blijft gelijk over de jaren heen. Daarop worden edities met elkaar vergeleken, dus
        hernoem je een product gerust, maar wijzig de slug niet.
      </p>
      <p v-if="tab === 'products'" class="muted small">
        <strong>Verpakking</strong> en <strong>stuks erin</strong> beschrijven hoe je inkoopt: een
        bak van 24, een doos van 6. Het inkoopadvies rondt daarmee af naar boven naar hele
        verpakkingen, want je koopt geen halve bak en je brengt er ook geen halve terug. De
        inkoopprijs geldt per stuk, niet per verpakking.
      </p>
    </section>

    <section class="card">
      <h2>{{ TABS.find(([k]) => k === tab)?.[1] }}</h2>
      <table v-if="tab === 'products'">
        <thead>
          <tr>
            <th>Naam</th><th>Slug</th><th>Bonnetjes</th><th>Inkoop €</th>
            <th>Verpakking</th><th>Stuks erin</th>
            <th v-for="b in barsForEdition" :key="b.id">{{ b.name }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>{{ r.name }}</td>
            <td class="muted">{{ r.slug }}</td>
            <td><input class="mini" type="number" :value="r.price_coupons"
                       @change="patch(r, 'price_coupons', Number(($event.target as HTMLInputElement).value))" /></td>
            <td><input class="mini" type="number" step="0.01" :value="r.cost_price_eur ?? ''"
                       @change="patch(r, 'cost_price_eur', Number(($event.target as HTMLInputElement).value) || null)" /></td>
            <td><input class="mini" :value="(r.purchase_unit as {name?:string})?.name ?? ''" placeholder="bak"
                       @change="patch(r, 'purchase_unit', { name: ($event.target as HTMLInputElement).value,
                                 size: (r.purchase_unit as {size?:number})?.size ?? 24 })" /></td>
            <td><input class="mini" type="number" :value="(r.purchase_unit as {size?:number})?.size ?? ''"
                       @change="patch(r, 'purchase_unit', { name: (r.purchase_unit as {name?:string})?.name ?? 'bak',
                                 size: Number(($event.target as HTMLInputElement).value) })" /></td>
            <td v-for="b in barsForEdition" :key="b.id">
              <input type="checkbox" :checked="((r.available_at as string[]) ?? []).includes(b.id as string)"
                     @change="toggleBar(r, b.id as string)" />
            </td>
            <td><button @click="remove(r)">Verwijderen</button></td>
          </tr>
        </tbody>
      </table>

      <table v-else>
        <thead>
          <tr>
            <th>Naam</th>
            <th v-if="tab === 'devices'">Laatst gezien</th>

            <th v-if="tab === 'editions'">Waarde bonnetje</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>{{ r.name ?? r.label }}</td>
            <td v-if="tab === 'devices'" class="muted">
              {{ r.last_seen_at ? new Date(r.last_seen_at as string).toLocaleString('nl-BE') : 'nog nooit' }}
            </td>

            <td v-if="tab === 'editions'">€ {{ r.coupon_value_eur }}</td>
            <td class="actions">
              <button v-if="tab === 'devices'" @click="rotate(r)">Nieuwe code</button>
              <button @click="remove(r)">
                {{ tab === 'devices' ? 'Intrekken' : 'Verwijderen' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.tabs { display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }
.tabs .on { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
.form { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; }
.form label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--ink-dim); }
.mini { width: 84px; }
.error { color: var(--bad); font-weight: 600; }
.actions { display: flex; gap: 8px; justify-content: flex-end; }
.token code {
  display: block; margin: 10px 0; padding: 12px; border-radius: 8px;
  background: var(--surface); border: 1px solid var(--line);
  font-size: 16px; word-break: break-all;
}
.small { font-size: 13px; margin-top: 10px; }
</style>
