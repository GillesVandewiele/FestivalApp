<script setup lang="ts">
import { computed, ref } from 'vue'
import { useFittedRows } from '../composables/useFittedRows'
import type { Category, Product } from '../stores/session'
import ProductButton from './ProductButton.vue'

const props = defineProps<{
  products: Product[]
  categories: Category[]
  qtyOf: (id: string) => number
  soldOut: Set<string>
  stockMode?: boolean
}>()
defineEmits<{ add: [Product]; remove: [Product] }>()

/**
 * One row per category, in the order the organiser set. Staff learn where a drink
 * lives by position, which is faster than reading a twelve-button grid.
 *
 * Products whose category no longer exists still appear, in a trailing group, rather
 * than vanishing from the till because somebody renamed a category.
 */
const groups = computed(() => {
  const known = props.categories.map((c) => ({
    key: c.slug,
    name: c.name,
    colour: c.colour,
    items: props.products.filter((p) => p.category === c.slug),
  }))
  const slugs = new Set(props.categories.map((c) => c.slug))
  const orphans = props.products.filter((p) => !slugs.has(p.category))
  if (orphans.length) {
    known.push({ key: '__other', name: 'Overige', colour: '#8b8178', items: orphans })
  }
  return known.filter((g) => g.items.length > 0)
})

// Staff should never scroll to find a drink: the row that is off-screen is the row
// nobody sells from. Button height is measured from the space available rather than
// fixed, so the whole till fits however many categories there are.
const MIN_COLUMN_PX = 150
// Two drinks in a category must not become two 900px slabs.
const MAX_COLUMN_PX = 240
const rows = ref<HTMLElement>()
const fit = computed(() => ({
  groupSizes: groups.value.map((g) => g.items.length),
  minColumnPx: MIN_COLUMN_PX,
  gapPx: 10,
  headingPx: 26,
  sectionGapPx: 14,
  minRowPx: 64,
  maxRowPx: 132,
}))
const { rowHeight, columns, fits } = useFittedRows(rows, fit)

/**
 * The column count is set explicitly rather than left to `auto-fill`.
 *
 * `auto-fill` twice produced a count that did not match the measurement: with a
 * definite max it sized repetitions from the max and overflowed a phone, and with
 * `1fr` it packed four tracks into a box meant for three. The fit is already
 * computed, so the grid is simply told the answer, and a max width keeps a button
 * from becoming a slab when there is room to spare.
 */
const gridMaxWidth = computed(() => `${columns.value * (MAX_COLUMN_PX + 10) - 10}px`)
</script>

<template>
  <div
    ref="rows"
    class="rows"
    :class="{ scrolls: !fits }"
    :style="{
      '--row-h': `${rowHeight}px`,
      '--col-min': `${MIN_COLUMN_PX}px`,
      '--cols': columns,
      '--grid-max': gridMaxWidth,
    }"
  >
    <section v-for="g in groups" :key="g.key" class="row">
      <h2 :style="{ '--tint': g.colour }">{{ g.name }}</h2>
      <div class="grid">
        <ProductButton
          v-for="p in g.items"
          :key="p.id"
          :product="p"
          :colour="g.colour"
          :qty="qtyOf(p.id)"
          :sold-out="soldOut.has(p.id)"
          :stock-mode="stockMode"
          @add="$emit('add', p)"
          @remove="$emit('remove', p)"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.rows {
  flex: 1;
  min-height: 0;
  overflow: hidden; /* the fit is computed; nothing should need to scroll */
  padding: var(--gap);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
/* Only when even the smallest usable button will not fit. A button too small to hit
   is worse than a scrollbar. */
.rows.scrolls {
  overflow-y: auto;
}
h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-dim);
}
h2::before {
  content: '';
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: var(--tint);
}
.grid {
  display: grid;
  /* min() so a very narrow screen still gets one full-width column instead of
     overflowing sideways. */
  grid-template-columns: repeat(var(--cols), minmax(0, 1fr));
  grid-auto-rows: var(--row-h);
  gap: var(--gap);
  max-width: var(--grid-max);
}
</style>
