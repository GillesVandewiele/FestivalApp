import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuth } from './auth'

export interface Edition {
  id: string
  name: string
  year: number
  coupon_value_eur: number
  timezone: string
  is_active: boolean
}

export const useEditions = defineStore('editions', () => {
  const all = ref<Edition[]>([])
  const currentId = ref<string | null>(null)

  async function load(): Promise<void> {
    const auth = useAuth()
    all.value = ((await auth.client.list('editions')) as Edition[]).sort(
      (a, b) => b.year - a.year,
    )
    if (!currentId.value && all.value.length) currentId.value = all.value[0].id
  }

  function byId(id: string | null): Edition | undefined {
    return all.value.find((e) => e.id === id)
  }

  return { all, currentId, load, byId }
})
