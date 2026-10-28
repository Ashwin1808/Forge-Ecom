import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, errorMessage, isApiError } from '../api/client'
import type { Product } from '../api/types'
import { EmptyState, ErrorBanner } from '../components/Feedback'
import { ArrowLeftIcon, ArrowRightIcon, CartIcon, MinusIcon, PlusIcon } from '../components/Icons'
import { formatMoney } from '../lib/format'
import { useCart } from '../store/cartState'

function productInitials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function StoreProductPage() {
  const { productId } = useParams<{ productId: string }>()
  const { add, itemCount } = useCart()
  const [product, setProduct] = useState<Product | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{
    message: string
    requestId: string | null
    notFound: boolean
  } | null>(null)
  const [reload, setReload] = useState(0)
  const [quantity, setQuantity] = useState(1)
  const [added, setAdded] = useState(false)

  useEffect(() => {
    if (!productId) return
    let active = true

    api
      .getProduct(productId)
      .then((result) => {
        if (!active) return
        setProduct(result)
        setQuantity(1)
      })
      .catch((caught: unknown) => {
        if (!active) return
        setError({
          message:
            isApiError(caught) && caught.status === 404
              ? 'This product is no longer available.'
              : errorMessage(caught),
          requestId: isApiError(caught) ? caught.requestId : null,
          notFound: caught instanceof ApiError && caught.status === 404,
        })
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [productId, reload])

  const retry = () => {
    setLoading(true)
    setError(null)
    setAdded(false)
    setReload((value) => value + 1)
  }

  if (loading) {
    return (
      <div className="store-stack">
        <div className="store-detail store-detail-loading" role="status" aria-label="Loading product">
          <span className="skeleton store-detail-skeleton-visual" />
          <div className="store-detail-info">
            <span className="skeleton skeleton-short" />
            <span className="skeleton skeleton-wide" />
            <span className="skeleton" />
          </div>
        </div>
      </div>
    )
  }

  if (error?.notFound) {
    return (
      <div className="store-stack">
        <EmptyState
          title="Product not found"
          description={error.message}
          action={
            <Link className="button button-primary button-small" to="/store">
              <ArrowLeftIcon /> Back to shop
            </Link>
          }
        />
      </div>
    )
  }

  if (error) {
    return (
      <div className="store-stack">
        <ErrorBanner
          message={error.message}
          requestId={error.requestId}
          onRetry={retry}
        />
        <Link className="text-link" to="/store">
          <ArrowLeftIcon /> Back to shop
        </Link>
      </div>
    )
  }

  if (!product) return null

  const maxQuantity = Math.max(1, product.quantity_available)
  const canAdd = product.quantity_available > 0 && quantity <= maxQuantity

  return (
    <div className="store-stack">
      <Link className="text-link store-back-link" to="/store">
        <ArrowLeftIcon /> Back to shop
      </Link>

      <section className="store-detail">
        <div className="store-detail-visual" aria-hidden="true">
          <span>{productInitials(product.name)}</span>
          <p>{product.sku}</p>
        </div>

        <div className="store-detail-info">
          <p className="store-eyebrow">{product.sku}</p>
          <h1>{product.name}</h1>
          <p className="store-description">
            {product.description ?? 'A considered addition to your everyday setup.'}
          </p>
          <p className="store-detail-price">
            {formatMoney(product.price_cents, product.currency)}
          </p>
          <p className={`store-stock${product.quantity_available === 0 ? ' out' : ''}`}>
            {product.quantity_available === 0
              ? 'Out of stock'
              : `${product.quantity_available} available`}
          </p>

          <div className="store-quantity-row">
            <label className="store-quantity">
              <span>Quantity</span>
              <div className="store-quantity-control">
                <button
                  type="button"
                  className="button button-secondary button-icon"
                  onClick={() => setQuantity((value) => Math.max(1, value - 1))}
                  disabled={quantity <= 1}
                  aria-label="Decrease quantity"
                >
                  <MinusIcon />
                </button>
                <input
                  type="number"
                  min={1}
                  max={maxQuantity}
                  value={quantity}
                  onChange={(event) => {
                    const next = Number(event.target.value)
                    setQuantity(
                      Number.isFinite(next)
                        ? Math.max(1, Math.min(maxQuantity, Math.floor(next)))
                        : 1,
                    )
                  }}
                  aria-label="Quantity"
                />
                <button
                  type="button"
                  className="button button-secondary button-icon"
                  onClick={() =>
                    setQuantity((value) => Math.min(maxQuantity, value + 1))
                  }
                  disabled={quantity >= maxQuantity}
                  aria-label="Increase quantity"
                >
                  <PlusIcon />
                </button>
              </div>
            </label>
          </div>

          <div className="store-detail-actions">
            <button
              type="button"
              className="button button-primary"
              onClick={() => {
                add(product, quantity)
                setAdded(true)
              }}
              disabled={!canAdd}
            >
              <CartIcon /> Add to cart
            </button>
            <Link className="button button-secondary" to="/store/cart">
              View cart ({itemCount})
            </Link>
          </div>

          {added && (
            <p className="store-notice" role="status">
              Added {quantity} to your cart.{' '}
              <Link className="text-link" to="/store/cart">
                Checkout <ArrowRightIcon />
              </Link>
            </p>
          )}
        </div>
      </section>
    </div>
  )
}
