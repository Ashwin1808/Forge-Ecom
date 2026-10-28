import type {
  CheckoutPayload,
  CreateOrderPayload,
  HealthStatus,
  Order,
  OrderList,
  OrderStatus,
  Product,
  ProductList,
} from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
const REQUEST_TIMEOUT_MS = 15_000

interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    details?: unknown
  }
  request_id?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null
  readonly details: unknown

  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null = null,
    details: unknown = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.details = details
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      signal: init.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new ApiError(0, 'timeout', 'The request timed out. Please try again.')
    }
    throw new ApiError(
      0,
      'network_error',
      'Unable to reach the Forge API. Check that the services are running.',
    )
  }

  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = null
    }
  }

  if (!response.ok) {
    const errorBody = body as ApiErrorBody | null
    throw new ApiError(
      response.status,
      errorBody?.error?.code ?? 'request_failed',
      errorBody?.error?.message ?? 'The request failed.',
      errorBody?.request_id ?? response.headers.get('X-Request-ID'),
      errorBody?.error?.details ?? null,
    )
  }

  return body as T
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const serialized = search.toString()
  return serialized ? `?${serialized}` : ''
}

export const api = {
  health(): Promise<HealthStatus> {
    return request<HealthStatus>('/health')
  },

  listProducts(params: { page?: number; page_size?: number } = {}): Promise<ProductList> {
    return request<ProductList>(
      `/api/v1/products${query({ page: params.page ?? 1, page_size: params.page_size ?? 20 })}`,
    )
  },

  getProduct(productId: string): Promise<Product> {
    return request<Product>(`/api/v1/products/${encodeURIComponent(productId)}`)
  },

  listOrders(
    params: { page?: number; page_size?: number; status?: OrderStatus } = {},
  ): Promise<OrderList> {
    return request<OrderList>(
      `/api/v1/orders${query({
        page: params.page ?? 1,
        page_size: params.page_size ?? 20,
        status: params.status,
      })}`,
    )
  },

  getOrder(orderId: string): Promise<Order> {
    return request<Order>(`/api/v1/orders/${encodeURIComponent(orderId)}`)
  },

  createOrder(payload: CreateOrderPayload, idempotencyKey: string): Promise<Order> {
    return request<Order>('/api/v1/orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    })
  },

  createCheckout(payload: CheckoutPayload, idempotencyKey: string): Promise<Order> {
    return request<Order>('/api/v1/storefront/checkout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    })
  },

  getStorefrontOrder(orderId: string): Promise<Order> {
    return request<Order>(
      `/api/v1/storefront/orders/${encodeURIComponent(orderId)}`,
    )
  },
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function errorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.message
  }
  return 'Something went wrong. Please try again.'
}
