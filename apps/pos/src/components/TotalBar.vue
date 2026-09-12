<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ total: number; canUndo: boolean; staffMode?: boolean }>()
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
    <!--
      Always rendered, disabled when there is nothing to undo. Showing it only after
      the first sale made it undiscoverable, and made the bar jump when it appeared.
    -->
    <button
      data-test="undo"
      class="undo"
      :disabled="!canUndo"
      aria-label="Laatste bestelling ongedaan maken"
      @click="emit('undo')"
    >
      <span class="glyph">&#8630;</span>
      <span class="word">ongedaan</span>
    </button>

    <button
      data-test="commit"
      class="commit"
      :class="{ idle: total === 0, staff: staffMode }"
      :disabled="total === 0"
      @click="commit"
    >
      <template v-if="staffMode">
        <span class="unit">personeel &middot; geen bonnetjes</span>
      </template>
      <template v-else>
        <span class="tnum">{{ total }}</span>
        <span class="unit">{{ total === 1 ? 'bonnetje' : 'bonnetjes' }}</span>
      </template>
      <span v-if="total > 0" class="tick">&check;</span>
    </button>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  gap: var(--gap);
  padding: var(--gap);
  border-top: 1px solid var(--line);
}
.undo {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  width: 104px;
  min-height: 74px;
  border: 1px solid var(--undo);
  border-radius: var(--radius);
  background: transparent;
  color: var(--undo);
  font: inherit;
  cursor: pointer;
}
.undo .glyph {
  font-size: 24px;
  line-height: 1;
}
.undo .word {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.undo:disabled {
  border-color: var(--line);
  color: var(--text-dim);
  opacity: 0.5;
  cursor: default;
}
.undo:active:not(:disabled) {
  background: color-mix(in srgb, var(--undo) 16%, transparent);
}
.commit {
  position: relative;
  flex: 1;
  min-height: 74px;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 12px;
  border: none;
  border-radius: var(--radius);
  background: var(--commit);
  color: var(--commit-ink);
  font: inherit;
  cursor: pointer;
}
.commit .tnum {
  font-size: 44px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.commit .unit {
  font-size: 22px;
  font-weight: 600;
}
.commit .tick {
  position: absolute;
  right: 22px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 28px;
  font-weight: 700;
}
.commit.staff {
  background: var(--staff);
  color: #17130f;
}
.commit.idle {
  background: var(--surface);
  color: var(--text-dim);
  cursor: default;
}
.commit:active:not(.idle) {
  filter: brightness(0.92);
}
.commit:focus-visible,
.undo:focus-visible {
  outline: 3px solid var(--text);
  outline-offset: 2px;
}
</style>
