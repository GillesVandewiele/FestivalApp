<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ error: string; queued?: number }>()
const emit = defineEmits<{ enrol: [string] }>()

const token = ref('')
const busy = ref(false)

async function submit() {
  if (!token.value.trim() || busy.value) return
  busy.value = true
  emit('enrol', token.value.trim())
  busy.value = false
}
</script>

<template>
  <form class="enrol" @submit.prevent="submit">
    <h1>Tablet koppelen</h1>
    <p>Plak de apparaatcode uit de beheerdersapp. Dit hoeft maar één keer.</p>
    <p v-if="queued" class="queued">
      Er {{ queued === 1 ? 'staat' : 'staan' }} nog {{ queued }}
      {{ queued === 1 ? 'bestelling' : 'bestellingen' }} klaar op deze tablet. Die
      {{ queued === 1 ? 'wordt' : 'worden' }} verstuurd zodra de koppeling weer werkt, en
      {{ queued === 1 ? 'gaat' : 'gaan' }} niet verloren.
    </p>
    <input
      v-model="token"
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
      placeholder="apparaatcode"
    />
    <button type="submit" :disabled="!token.trim() || busy">Koppelen</button>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<style scoped>
.enrol {
  padding: 32px;
  max-width: 540px;
}
h1 {
  font-size: 28px;
  font-weight: 800;
  margin: 0 0 8px;
}
p {
  color: var(--text-dim);
  font-weight: 500;
  margin: 0;
}
input {
  width: 100%;
  min-height: var(--tap);
  margin: 18px 0;
  padding: 0 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 18px;
}
input:focus-visible {
  outline: 3px solid var(--text);
  outline-offset: 2px;
}
button {
  min-height: var(--tap);
  width: 100%;
  border: none;
  border-radius: var(--radius);
  background: var(--commit);
  color: var(--commit-ink);
  font: inherit;
  font-size: 21px;
  font-weight: 800;
}
button:disabled {
  background: var(--surface);
  color: var(--text-dim);
}
.error {
  margin-top: 14px;
  color: var(--undo);
  font-weight: 600;
}
</style>
