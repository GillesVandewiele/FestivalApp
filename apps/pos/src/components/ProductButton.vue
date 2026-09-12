<script setup lang="ts">
import { computed } from 'vue'
import type { Product } from '../stores/session'

const props = defineProps<{ product: Product; qty: number; soldOut: boolean }>()
defineEmits<{ add: [] }>()

const CATEGORY_COLOURS: Record<string, string> = {
  bier: 'var(--cat-bier)',
  wijn: 'var(--cat-wijn)',
  cocktail: 'var(--cat-cocktail)',
  fris: 'var(--cat-fris)',
  warm: 'var(--cat-warm)',
}

const tint = computed(() => CATEGORY_COLOURS[props.product.category] ?? 'var(--cat-default)')
</script>

<template>
  <button
    class="product"
    :class="{ 'is-out': soldOut, 'has-qty': qty > 0 }"
    :style="{ '--tint': tint }"
    :disabled="soldOut"
    :aria-label="`${product.name}, ${product.price_coupons} bonnetjes`"
    @click="$emit('add')"
  >
    <span class="name">{{ product.name }}</span>
    <span class="price tnum">{{ product.price_coupons }}</span>
    <span v-if="qty > 0" class="qty tnum">{{ qty }}</span>
    <span v-if="soldOut" class="out">op</span>
  </button>
</template>

<style scoped>
.product {
  position: relative;
  min-height: var(--tap);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 14px 8px;
  border: none;
  border-left: 6px solid var(--tint);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.product:active:not(:disabled) {
  background: var(--surface-press);
}
.product:focus-visible {
  outline: 3px solid var(--text);
  outline-offset: 2px;
}
.product.has-qty {
  background: color-mix(in srgb, var(--tint) 22%, var(--surface));
}
.product.is-out {
  opacity: 0.3;
}
.name {
  font-size: 20px;
  font-weight: 700;
  text-align: center;
  line-height: 1.1;
}
/* The price reads as a coupon count, so the unit is a ticket glyph rather than
   the word repeated on every one of ten buttons. */
.price {
  color: var(--text-dim);
  font-size: 15px;
  font-weight: 500;
}
.price::after {
  content: ' 🎫';
}
.qty {
  position: absolute;
  top: 6px;
  right: 8px;
  min-width: 30px;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--tint);
  color: #17130f;
  font-size: 17px;
  font-weight: 800;
}
.out {
  position: absolute;
  top: 8px;
  left: 10px;
  color: var(--undo);
  font-size: 13px;
  font-weight: 700;
}
</style>
