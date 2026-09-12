<script setup lang="ts">
import type { Product } from '../stores/session'
import ProductButton from './ProductButton.vue'

defineProps<{
  products: Product[]
  qtyOf: (id: string) => number
  soldOut: Set<string>
}>()
defineEmits<{ add: [Product]; remove: [Product] }>()
</script>

<template>
  <div class="grid">
    <ProductButton
      v-for="p in products"
      :key="p.id"
      :product="p"
      :qty="qtyOf(p.id)"
      :sold-out="soldOut.has(p.id)"
      @add="$emit('add', p)"
      @remove="$emit('remove', p)"
    />
  </div>
</template>

<style scoped>
/*
  Fixed row height. Previously the rows were 1fr of a flex-grown container, so ten
  products in a single row became 950px-tall columns on a desktop screen.
*/
.grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  grid-auto-rows: clamp(100px, 16vh, 140px);
  align-content: start;
  gap: var(--gap);
  padding: var(--gap);
  overflow-y: auto;
}
</style>
