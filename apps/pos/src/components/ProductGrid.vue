<script setup lang="ts">
import { computed } from 'vue'
import type { Category, Product } from '../stores/session'
import ProductButton from './ProductButton.vue'

const props = defineProps<{
  products: Product[]
  categories: Category[]
  qtyOf: (id: string) => number
  soldOut: Set<string>
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
</script>

<template>
  <div class="rows">
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
  overflow-y: auto;
  padding: var(--gap);
  display: flex;
  flex-direction: column;
  gap: 14px;
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
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  grid-auto-rows: clamp(92px, 13vh, 124px);
  gap: var(--gap);
}
</style>
