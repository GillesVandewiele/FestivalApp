<script setup lang="ts">
import type { Product } from '../stores/session'
import ProductButton from './ProductButton.vue'

defineProps<{
  products: Product[]
  qtyOf: (id: string) => number
  soldOut: Set<string>
}>()
defineEmits<{ add: [Product] }>()
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
    />
  </div>
</template>

<style scoped>
.grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  grid-auto-rows: minmax(var(--tap), 1fr);
  gap: var(--gap);
  padding: var(--gap);
  overflow-y: auto;
}
</style>
