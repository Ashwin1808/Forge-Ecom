export type OrderStatus =
  | 'PENDING'
  | 'AWAITING_PAYMENT'
  | 'CONFIRMED'
  | 'FAILED'
  | 'EXPIRED'

export type PaymentStatus =
  | 'CREATED'
  | 'PENDING'
  | 'PAID'
  | 'FAILED'
  | 'REFUNDED'

export type OrderChannel = 'OPS' | 'STOREFRONT'

export interface Customer {
  name: string
  email: string
}

export interface DeliveryAddress {
  line1: string
  line2: string | null
  city: string
  region: string | null
  postal_code: string
  country: string
}

export interface OrderItem {
  product_id: string
  sku: string | null
  name: string | null
  quantity: number
  unit_price_cents: number | null
  currency: string | null
  line_total_cents: number | null
}

export interface Order {
  id: string
  status: OrderStatus
  payment_status: PaymentStatus | null
  channel: OrderChannel
  customer: Customer
  delivery_address: DeliveryAddress | null
  items: OrderItem[]
  total_cents: number | null
  currency: string
  reservation_expires_at: string | null
  failure_code: string | null
  failure_message: string | null
  created_at: string
  updated_at: string
}

export interface OrderList {
  items: Order[]
  page: number
  page_size: number
  total: number
}

export interface Product {
  id: string
  sku: string
  name: string
  description: string | null
  price_cents: number
  currency: string
  quantity_available: number
  quantity_reserved: number
  in_stock: boolean
  created_at: string
}

export interface ProductList {
  items: Product[]
  page: number
  page_size: number
  total: number
}

export interface HealthStatus {
  status: string
  service: string
  version: string
  environment: string
}

export interface CreateOrderPayload {
  customer: Customer
  items: Array<{ product_id: string; quantity: number }>
}

export interface CheckoutPayload {
  customer: Customer
  delivery_address: {
    line1: string
    line2?: string | null
    city: string
    region?: string | null
    postal_code: string
    country: string
  }
  items: Array<{ product_id: string; quantity: number }>
}
