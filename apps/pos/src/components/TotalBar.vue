<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ total: number; canUndo: boolean }>()
const emit = defineEmits<{ commit: []; undo: [] }>()

const DEBOUNCE_MS = 400
const locked = ref(false)

/** A double-tap on the commit slab must never produce two sales. */
function commit() {
  if (props.total === 0 || locked.value) return
  locked.value = true
  emit('commit')
  setTimeout(() => (locked.value = false), DEBOUNCE_MS)
}
</script>

<template>
  <div class="bar">
    <button
      v-if="canUndo"
      data-test="undo"
      class="undo"
      aria-label="Laatste bestelling ongedaan maken"
      @click="emit('undo')"
    >
      &#8630;
    </button>
    <button
      data-test="commit"
      class="commit"
      :class="{ idle: total === 0 }"
      :disabled="total === 0"
      @click="commit"
    >
      <span class="tnum">{{ total }}</span>
      {{ total === 1 ? 'bonnetje' : 'bonnetjes' }}
    </button>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  gap: var(--gap);
  padding: var(--gap);
}
.undo {
  width: 84px;
  min-height: 88px;
  border: 2px solid var(--undo);
  border-radius: var(--radius);
  background: transparent;
  color: var(--undo);
  font: inherit;
  font-size: 30px;
}
.undo:active {
  background: color-mix(in srgb, var(--undo) 18%, transparent);
}
.commit {
  flex: 1;
  min-height: 88px;
  border: none;
  border-radius: var(--radius);
  background: var(--commit);
  color: var(--commit-ink);
  font: inherit;
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.01em;
}
.commit .tnum {
  font-size: 56px;
  margin-right: 10px;
}
.commit.idle {
  background: var(--surface);
  color: var(--text-dim);
}
.commit:active:not(.idle) {
  filter: brightness(0.9);
}
.commit:focus-visible,
.undo:focus-visible {
  outline: 3px solid var(--text);
  outline-offset: 2px;
}
</style>
