export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export interface User {
  id: string
  email: string
  role: string
}

export function createClient(baseUrl = '', fetchImpl: typeof fetch = globalThis.fetch) {
  async function request(path: string, init: RequestInit = {}) {
    const response = await fetchImpl(`${baseUrl}${path}`, {
      ...init,
      credentials: 'include', // the session is an HttpOnly cookie
      headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    })
    if (!response.ok) throw new ApiError(response.status, await response.text())
    if (response.status === 204) return null
    return response.json()
  }

  function query(params: Record<string, string | number | undefined>) {
    const pairs = Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
    return new URLSearchParams(pairs.map(([k, v]) => [k, String(v)])).toString()
  }

  return {
    login: (email: string, password: string): Promise<User> =>
      request('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
    logout: () => request('/api/v1/auth/logout', { method: 'POST' }),
    me: (): Promise<User> => request('/api/v1/auth/me'),

    list: (resource: string, editionId?: string) =>
      request(`/api/v1/admin/${resource}${editionId ? `?edition_id=${editionId}` : ''}`),
    create: (resource: string, body: unknown) =>
      request(`/api/v1/admin/${resource}`, { method: 'POST', body: JSON.stringify(body) }),
    update: (resource: string, id: string, body: unknown) =>
      request(`/api/v1/admin/${resource}/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (resource: string, id: string) =>
      request(`/api/v1/admin/${resource}/${id}`, { method: 'DELETE' }),

    enrollDevice: (body: { edition_id: string; bar_id: string; label: string }) =>
      request('/api/v1/admin/devices/enroll', { method: 'POST', body: JSON.stringify(body) }),
    listDevices: () => request('/api/v1/admin/devices'),
    rotateDevice: (id: string) =>
      request(`/api/v1/admin/devices/${id}/rotate`, { method: 'POST' }),
    revokeDevice: (id: string) =>
      request(`/api/v1/admin/devices/${id}/revoke`, { method: 'POST' }),

    stats: (name: string, params: Record<string, string | number | undefined>) =>
      request(`/api/v1/stats/${name}?${query(params)}`),
    csvUrl: (report: string, editionId: string) =>
      `${baseUrl}/api/v1/export/${report}.csv?edition_id=${editionId}`,
  }
}

export type Client = ReturnType<typeof createClient>
