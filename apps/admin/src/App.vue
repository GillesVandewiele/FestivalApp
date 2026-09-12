<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()

async function signOut() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="shell">
    <nav v-if="auth.user" class="top">
      <strong>Festival beheer</strong>
      <RouterLink to="/live" :class="{ on: route.path === '/live' }">Live</RouterLink>
      <RouterLink to="/reports" :class="{ on: route.path === '/reports' }">Rapporten</RouterLink>
      <RouterLink to="/config" :class="{ on: route.path === '/config' }">Instellingen</RouterLink>
      <button class="out" @click="signOut">Afmelden</button>
    </nav>
    <main :class="{ padded: !!auth.user }">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.top {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 12px 22px;
  border-bottom: 1px solid var(--line);
  background: var(--surface-2);
}
.top a {
  color: var(--ink-dim);
  text-decoration: none;
  font-weight: 600;
}
.top a.on {
  color: var(--ink);
}
.out {
  margin-left: auto;
}
.padded {
  padding: 22px;
  max-width: 1280px;
  margin: 0 auto;
}
</style>
