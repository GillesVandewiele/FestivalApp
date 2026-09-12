<script setup lang="ts">
defineProps<{ label: string; value: string; note?: string }>()
</script>

<template>
  <div class="tile">
    <span class="label">{{ label }}</span>
    <strong class="value">{{ value }}</strong>
    <span v-if="note" class="note">{{ note }}</span>
  </div>
</template>

<style scoped>
.tile {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 14px 16px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.label {
  color: var(--ink-dim);
  font-size: 13px;
}
.value {
  font-size: 30px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
}
.note {
  color: var(--ink-dim);
  font-size: 12px;
}
</style>
