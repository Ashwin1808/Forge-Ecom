import { createContext, useContext } from 'react'
import type { Product } from '../api/types'

export interface CartItem {
  productId: string
  sku: string
  name: string
  priceCents: number
  currency: string
  quantity: number
  quantityAvailable: number
}

export interface CartContextValue {
  items: CartItem[]
  itemCount: number
  subtotalCents: number
  currency: string
  add: (product: Product, quantity?: number) => void
  updateQuantity: (productId: string, quantity: number) => void
  remove: (productId: string) => void
  clear: () => void
}

export const CartContext = createContext<CartContextValue | null>(null)

export function useCart(): CartContextValue {
  const value = useContext(CartContext)
  if (!value) {
    throw new Error('useCart must be used inside CartProvider')
  }
  return value
}
