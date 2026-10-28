import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Product } from '../api/types'
import { CartContext } from './cartState'
import type { CartContextValue, CartItem } from './cartState'

const STORAGE_KEY = 'forge-store-cart-v1'

function isCartItem(value: unknown): value is CartItem {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    typeof item.productId === 'string' &&
    typeof item.sku === 'string' &&
    typeof item.name === 'string' &&
    typeof item.priceCents === 'number' &&
    typeof item.currency === 'string' &&
    typeof item.quantity === 'number' &&
    Number.isInteger(item.quantity) &&
    item.quantity > 0 &&
    typeof item.quantityAvailable === 'number'
  )
}

function loadCart(): CartItem[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter(isCartItem) : []
  } catch {
    return []
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(loadCart)

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
    } catch {
      // Storage may be unavailable in private browsing; the cart still works in memory.
    }
  }, [items])

  const add = useCallback((product: Product, quantity = 1) => {
    if (quantity < 1 || product.quantity_available < 1) return
    setItems((current) => {
      const existing = current.find((item) => item.productId === product.id)
      if (existing) {
        return current.map((item) =>
          item.productId === product.id
            ? {
                ...item,
                quantity: Math.min(
                  item.quantity + quantity,
                  product.quantity_available,
                ),
                quantityAvailable: product.quantity_available,
                priceCents: product.price_cents,
                name: product.name,
                sku: product.sku,
              }
            : item,
        )
      }
      return [
        ...current,
        {
          productId: product.id,
          sku: product.sku,
          name: product.name,
          priceCents: product.price_cents,
          currency: product.currency,
          quantity: Math.min(quantity, product.quantity_available),
          quantityAvailable: product.quantity_available,
        },
      ]
    })
  }, [])

  const updateQuantity = useCallback((productId: string, quantity: number) => {
    setItems((current) =>
      current
        .map((item) =>
          item.productId === productId
            ? {
                ...item,
                quantity: Math.max(
                  1,
                  Math.min(
                    Number.isFinite(quantity) ? Math.floor(quantity) : 1,
                    item.quantityAvailable,
                  ),
                ),
              }
            : item,
        )
        .filter((item) => item.quantity > 0),
    )
  }, [])

  const remove = useCallback((productId: string) => {
    setItems((current) =>
      current.filter((item) => item.productId !== productId),
    )
  }, [])

  const clear = useCallback(() => setItems([]), [])

  const value = useMemo<CartContextValue>(() => {
    const itemCount = items.reduce((total, item) => total + item.quantity, 0)
    const subtotalCents = items.reduce(
      (total, item) => total + item.priceCents * item.quantity,
      0,
    )
    return {
      items,
      itemCount,
      subtotalCents,
      currency: items[0]?.currency ?? 'USD',
      add,
      updateQuantity,
      remove,
      clear,
    }
  }, [add, clear, items, remove, updateQuantity])

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}
