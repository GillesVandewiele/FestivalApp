<script setup lang="ts">
import type { CartLine } from '../stores/cart'

defineProps<{ lines: CartLine[] }>()
defineEmits<{ remove: [string] }>()
</script>

<template>
  <!--
    Two jobs: let staff glance-check the round before taking coupons, and give
    "remove one" a real home. A tablet has no right-click and long-press is
    slow and unreliable, so decrementing has to be a plain tap somewhere.
  -->
  <div v-if="lines.length" class="strip">
    <button v-for="l in lines" :key="l.product.id" class="chip" @click="$emit('remove', l.product.id)">
      <span class="n tnum">{{ l.qty }}&times;</span>
      {{ l.product.name }}
      <span class="minus">&minus;</span>
    </button>
  </div>
</template>

<style scoped>
.strip {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 8px var(--gap) 0;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 46px;
  flex: 0 0 auto;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 16px;
  white-space: nowrap;
}
.chip:active {
  background: var(--surface-press);
}
.n {
  font-weight: 800;
}
.minus {
  color: var(--text-dim);
  font-size: 19px;
  line-height: 1;
}
</style>
