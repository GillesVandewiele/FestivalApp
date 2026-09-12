<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Product } from '../stores/session'

const props = defineProps<{ product: Product; qty: number; soldOut: boolean }>()
const emit = defineEmits<{ add: []; remove: [] }>()

const CATEGORY_COLOURS: Record<string, string> = {
  bier: 'var(--cat-bier)',
  wijn: 'var(--cat-wijn)',
  cocktail: 'var(--cat-cocktail)',
  fris: 'var(--cat-fris)',
  warm: 'var(--cat-warm)',
}

const LONG_PRESS_MS = 450
const tint = computed(() => CATEGORY_COLOURS[props.product.category] ?? 'var(--cat-default)')
const priceLabel = computed(() =>
  props.product.price_coupons === 1 ? '1 bon' : `${props.product.price_coupons} bonnen`,
)

// Hold to remove one. Works with a finger and with a mouse, so the gesture is the
// same on a tablet at the bar and on a laptop during setup.
let timer: ReturnType<typeof setTimeout> | undefined
const held = ref(false)

function down() {
  if (props.soldOut) return
  held.value = false
  timer = setTimeout(() => {
    held.value = true
    if (props.qty > 0) emit('remove')
  }, LONG_PRESS_MS)
}

function up() {
  clearTimeout(timer)
}

function click() {
  if (held.value) {
    held.value = false // the long press already removed one; do not add it back
    return
  }
  emit('add')
}
</script>

<template>
  <button
    class="product"
    :class="{ 'is-out': soldOut, 'has-qty': qty > 0 }"
    :style="{ '--tint': tint }"
    :disabled="soldOut"
    :aria-label="`${product.name}, ${priceLabel}${qty ? `, ${qty} in bestelling` : ''}`"
    @pointerdown="down"
    @pointerup="up"
    @pointerleave="up"
    @pointercancel="up"
    @click="click"
    @contextmenu.prevent="qty > 0 && emit('remove')"
  >
    <span class="name">{{ product.name }}</span>
    <span class="price">{{ priceLabel }}</span>
    <span v-if="qty > 0" class="qty tnum">{{ qty }}</span>
    <span v-if="soldOut" class="out">OP</span>
  </button>
</template>

<style scoped>
.product {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--tint) 34%, transparent);
  border-radius: var(--radius);
  background:
    linear-gradient(color-mix(in srgb, var(--tint) 7%, transparent),
                    color-mix(in srgb, var(--tint) 7%, transparent)),
    var(--surface);
  color: var(--text);
  font: inherit;
  cursor: pointer;
  transition: transform 0.06s ease;
}
.product::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  border-radius: var(--radius) 0 0 var(--radius);
  background: var(--tint);
}
.product:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--tint) 60%, transparent);
}
.product:active:not(:disabled) {
  transform: scale(0.98);
}
.product.has-qty {
  border-color: var(--tint);
  background:
    linear-gradient(color-mix(in srgb, var(--tint) 22%, transparent),
                    color-mix(in srgb, var(--tint) 22%, transparent)),
    var(--surface);
}
.product.is-out {
  opacity: 0.32;
}
.product:focus-visible {
  outline: 3px solid var(--text);
  outline-offset: 2px;
}
.name {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.15;
  text-align: center;
}
.price {
  color: var(--text-dim);
  font-size: 13px;
  font-weight: 500;
}
.qty {
  position: absolute;
  top: 7px;
  right: 8px;
  min-width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  padding: 0 7px;
  border-radius: 999px;
  background: var(--tint);
  color: #17130f;
  font-size: 15px;
  font-weight: 800;
}
.out {
  position: absolute;
  top: 9px;
  left: 12px;
  color: var(--undo);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.05em;
}
</style>
