import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from './auth'

beforeEach(() => setActivePinia(createPinia()))

describe('auth store', () => {
  it('stores the user after a successful login', async () => {
    const auth = useAuth()
    auth.client = {
      login: vi.fn().mockResolvedValue({ id: 'u1', email: 'a@b.c', role: 'organizer' }),
    } as never

    await auth.login('a@b.c', 'pw')

    expect(auth.user?.email).toBe('a@b.c')
    expect(auth.error).toBe('')
  })

  it('reports a Dutch error on bad credentials without storing a user', async () => {
    const auth = useAuth()
    auth.client = { login: vi.fn().mockRejectedValue({ status: 401 }) } as never

    await auth.login('a@b.c', 'wrong')

    expect(auth.user).toBeNull()
    expect(auth.error).toContain('onjuist')
  })

  it('distinguishes a server being unreachable from bad credentials', async () => {
    // A sleeping free-tier backend must not read as "wrong password".
    const auth = useAuth()
    auth.client = { login: vi.fn().mockRejectedValue(new TypeError('fetch failed')) } as never

    await auth.login('a@b.c', 'pw')

    expect(auth.error).toContain('bereikbaar')
  })

  it('clears the user on logout', async () => {
    const auth = useAuth()
    auth.client = {
      login: vi.fn().mockResolvedValue({ id: 'u1', email: 'a@b.c', role: 'organizer' }),
      logout: vi.fn().mockResolvedValue({}),
    } as never
    await auth.login('a@b.c', 'pw')

    await auth.logout()

    expect(auth.user).toBeNull()
  })
})
