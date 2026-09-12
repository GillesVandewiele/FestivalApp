<script setup lang="ts">
defineProps<{ staff: { id: string; name: string }[]; barName: string }>()
defineEmits<{ choose: [string]; unlink: [] }>()
</script>

<template>
  <div class="picker">
    <p class="bar">{{ barName }}</p>
    <h1>Wie staat er achter de toog?</h1>
    <div class="names">
      <button v-for="s in staff" :key="s.id" @click="$emit('choose', s.id)">{{ s.name }}</button>
    </div>
    <p v-if="!staff.length" class="empty">
      Nog geen medewerkers ingesteld. Voeg ze toe in de beheerdersapp.
    </p>
    <button class="unlink" @click="$emit('unlink')">Tablet ontkoppelen</button>
  </div>
</template>

<style scoped>
.picker {
  padding: 28px;
}
.bar {
  margin: 0;
  color: var(--text-dim);
  font-weight: 600;
}
h1 {
  font-size: 28px;
  font-weight: 800;
  margin: 4px 0 22px;
}
.names {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: var(--gap);
}
button {
  min-height: 92px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 23px;
  font-weight: 700;
}
button:active {
  background: var(--surface-press);
}
button:focus-visible {
  outline: 3px solid var(--text);
  outline-offset: 2px;
}
.empty {
  color: var(--text-dim);
  font-weight: 500;
}
/* The way back to the enrol screen. Deliberately quiet: it is a setup action, not
   something anyone needs mid-shift. */
.unlink {
  margin-top: 28px;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: transparent;
  color: var(--text-dim);
  font: inherit;
  font-size: 14px;
}
</style>
