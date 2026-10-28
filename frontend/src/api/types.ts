export type OrderStatus = 'PENDING' | 'CONFIRMED' | 'FAILED'

export interface Customer {
  name: string
  email: string
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
  customer: Customer
  items: OrderItem[]
  total_cents: number | null
  currency: string
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
