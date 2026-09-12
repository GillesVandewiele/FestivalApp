<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const email = ref('')
const password = ref('')

async function submit() {
  await auth.login(email.value, password.value)
  if (auth.user) router.push('/live')
}
</script>

<template>
  <form class="login" @submit.prevent="submit">
    <h1>Festival beheer</h1>
    <p class="muted">Meld je aan om verkoop te volgen en in te stellen.</p>
    <label>E-mailadres<input v-model="email" type="email" autocomplete="username" required /></label>
    <label>Wachtwoord
      <input v-model="password" type="password" autocomplete="current-password" required />
    </label>
    <button class="primary" type="submit" :disabled="auth.busy">
      {{ auth.busy ? 'Bezig…' : 'Aanmelden' }}
    </button>
    <p v-if="auth.error" class="error">{{ auth.error }}</p>
  </form>
</template>

<style scoped>
.login {
  max-width: 380px;
  margin: 12vh auto;
  padding: 0 20px;
}
label {
  display: block;
  margin: 16px 0;
  font-size: 14px;
  color: var(--ink-dim);
}
input {
  display: block;
  width: 100%;
  margin-top: 6px;
}
button {
  width: 100%;
}
.error {
  color: var(--bad);
  font-weight: 600;
}
</style>
