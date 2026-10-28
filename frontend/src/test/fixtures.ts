import type {
  DeliveryAddress,
  Order,
  OrderList,
  Product,
  ProductList,
} from '../api/types'

export const PRODUCT_LAMP: Product = {
  id: '11111111-1111-4111-8111-111111111111',
  sku: 'LAMP-001',
  name: 'Aurora Desk Lamp',
  description: 'Warm dimmable desk lamp',
  price_cents: 12900,
  currency: 'USD',
  quantity_available: 12,
  quantity_reserved: 2,
  in_stock: true,
  created_at: '2026-10-01T12:00:00Z',
}

export const PRODUCT_NOTEBOOK: Product = {
  id: '22222222-2222-4222-8222-222222222222',
  sku: 'NOTE-014',
  name: 'Foundry Notebook',
  description: 'Lay-flat dot grid notebook',
  price_cents: 2400,
  currency: 'USD',
  quantity_available: 3,
  quantity_reserved: 0,
  in_stock: true,
  created_at: '2026-10-02T12:00:00Z',
}

export const STORE_ADDRESS: DeliveryAddress = {
  line1: '1 Market Street',
  line2: 'Suite 200',
  city: 'San Francisco',
  region: 'CA',
  postal_code: '94105',
  country: 'US',
}

export const CONFIRMED_ORDER: Order = {
  id: '33333333-3333-4333-8333-333333333333',
  status: 'CONFIRMED',
  payment_status: null,
  channel: 'OPS',
  delivery_address: null,
  reservation_expires_at: null,
  customer: {
    name: 'Ada Lovelace',
    email: 'ada@example.com',
  },
  items: [
    {
      product_id: PRODUCT_LAMP.id,
      sku: PRODUCT_LAMP.sku,
      name: PRODUCT_LAMP.name,
      quantity: 2,
      unit_price_cents: 12900,
      currency: 'USD',
      line_total_cents: 25800,
    },
  ],
  total_cents: 25800,
  currency: 'USD',
  failure_code: null,
  failure_message: null,
  created_at: '2026-10-20T09:30:00Z',
  updated_at: '2026-10-20T09:30:01Z',
}

export const FAILED_ORDER: Order = {
  id: '44444444-4444-4444-8444-444444444444',
  status: 'FAILED',
  payment_status: null,
  channel: 'OPS',
  delivery_address: null,
  reservation_expires_at: null,
  customer: {
    name: 'Grace Hopper',
    email: 'grace@example.com',
  },
  items: [
    {
      product_id: PRODUCT_NOTEBOOK.id,
      sku: PRODUCT_NOTEBOOK.sku,
      name: PRODUCT_NOTEBOOK.name,
      quantity: 50,
      unit_price_cents: 2400,
      currency: 'USD',
      line_total_cents: 120000,
    },
  ],
  total_cents: 120000,
  currency: 'USD',
  failure_code: 'insufficient_inventory',
  failure_message: 'Insufficient inventory for Foundry Notebook.',
  created_at: '2026-10-21T10:00:00Z',
  updated_at: '2026-10-21T10:00:02Z',
}

export function makeProductList(items: Product[], total = items.length): ProductList {
  return {
    items,
    page: 1,
    page_size: 20,
    total,
  }
}

export function makeOrderList(items: Order[], total = items.length): OrderList {
  return {
    items,
    page: 1,
    page_size: 20,
    total,
  }
}

export const AWAITING_ORDER: Order = {
  id: '66666666-6666-4666-8666-666666666666',
  status: 'AWAITING_PAYMENT',
  payment_status: 'CREATED',
  channel: 'STOREFRONT',
  customer: {
    name: 'Grace Hopper',
    email: 'grace@example.com',
  },
  delivery_address: STORE_ADDRESS,
  items: [
    {
      product_id: PRODUCT_LAMP.id,
      sku: PRODUCT_LAMP.sku,
      name: PRODUCT_LAMP.name,
      quantity: 1,
      unit_price_cents: PRODUCT_LAMP.price_cents,
      currency: 'USD',
      line_total_cents: PRODUCT_LAMP.price_cents,
    },
  ],
  total_cents: PRODUCT_LAMP.price_cents,
  currency: 'USD',
  reservation_expires_at: '2026-10-28T18:15:00Z',
  failure_code: null,
  failure_message: null,
  created_at: '2026-10-28T18:00:00Z',
  updated_at: '2026-10-28T18:00:01Z',
}
