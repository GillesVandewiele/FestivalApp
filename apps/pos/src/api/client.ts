export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export interface OrderItemPayload {
  product_id: string
  slug: string
  name: string
  qty: number
  unit_price_coupons: number
}

export interface OrderPayload {
  id: string
  edition_id: string
  bar_id: string
  staff_id: string
  items: OrderItemPayload[]
  created_at: string
  status: 'confirmed' | 'voided'
  kind: 'sale' | 'staff'
  void?: { at: string; by: { type: 'staff'; id: string }; reason: string | null }
}

export interface StockoutPayload {
  id: string
  product_id: string
  out_at: string
  back_at: string | null
}

export interface SyncResult {
  accepted: string[]
  results: Record<string, string>
}

export function createClient(
  baseUrl: string,
  getToken: () => string | null,
  fetchImpl: typeof fetch = globalThis.fetch,
) {
  async function request(path: string, init: RequestInit = {}) {
    const token = getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`

    const response = await fetchImpl(`${baseUrl}${path}`, { ...init, headers })
    if (!response.ok) throw new ApiError(response.status, await response.text())
    return response.json()
  }

  return {
    getTime: () => request('/api/v1/time'),
    getBootstrap: () => request('/api/v1/bootstrap'),
    syncOrders: (orders: OrderPayload[]): Promise<SyncResult> =>
      request('/api/v1/sync/orders', { method: 'POST', body: JSON.stringify({ orders }) }),
    syncStockouts: (stockouts: StockoutPayload[]) =>
      request('/api/v1/sync/stockouts', { method: 'POST', body: JSON.stringify({ stockouts }) }),
  }
}
