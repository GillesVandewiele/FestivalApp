<script setup lang="ts">
import type { CartLine } from '../stores/cart'

defineProps<{ lines: CartLine[] }>()
defineEmits<{ remove: [string]; clear: [] }>()
</script>

<template>
  <!--
    Glance-check the round before taking coupons, and a plain tap to remove one.
    Long-pressing a product does the same, but this makes it visible.
  -->
  <div v-if="lines.length" class="strip">
    <button
      v-for="l in lines"
      :key="l.product.id"
      class="chip"
      @click="$emit('remove', l.product.id)"
    >
      <span class="n tnum">{{ l.qty }}&times;</span>
      {{ l.product.name }}
      <span class="minus">&minus;</span>
    </button>
    <button class="chip clear" @click="$emit('clear')">leegmaken</button>
  </div>
</template>

<style scoped>
.strip {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 0 var(--gap) 8px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 42px;
  flex: 0 0 auto;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 15px;
  white-space: nowrap;
  cursor: pointer;
}
.chip:active {
  background: var(--surface-press);
}
.n {
  font-weight: 800;
}
.minus {
  color: var(--text-dim);
  font-size: 18px;
  line-height: 1;
}
.clear {
  color: var(--text-dim);
  margin-left: auto;
}
</style>
