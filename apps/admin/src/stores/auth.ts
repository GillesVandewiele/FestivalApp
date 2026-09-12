import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import { createClient, type User } from '../api/client'

export const useAuth = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const error = ref('')
  const busy = ref(false)
  const checked = ref(false)
  const client = shallowRef(createClient())

  async function login(email: string, password: string): Promise<void> {
    busy.value = true
    error.value = ''
    try {
      user.value = await client.value.login(email, password)
    } catch (e) {
      user.value = null
      // A sleeping free-tier backend must not read as "wrong password", or the
      // organiser retypes their credentials at a server that is merely waking up.
      error.value =
        (e as { status?: number }).status === 401
          ? 'E-mailadres of wachtwoord is onjuist.'
          : 'Server niet bereikbaar. Probeer het over een minuut opnieuw.'
    } finally {
      busy.value = false
    }
  }

  async function logout(): Promise<void> {
    await client.value.logout()
    user.value = null
  }

  async function check(): Promise<void> {
    try {
      user.value = await client.value.me()
    } catch {
      user.value = null
    } finally {
      checked.value = true
    }
  }

  return { user, error, busy, checked, client, login, logout, check }
})
