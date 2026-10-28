import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage, isApiError } from '../api/client'
import type { Product, ProductList } from '../api/types'
import { EmptyState, ErrorBanner } from '../components/Feedback'
import { ArrowRightIcon, CartIcon, PlusIcon, RefreshIcon } from '../components/Icons'
import { formatMoney } from '../lib/format'
import { useCart } from '../store/cartState'

function productInitials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

function StoreProductCard({
  product,
  onAdd,
}: {
  product: Product
  onAdd: (product: Product) => void
}) {
  return (
    <article className="store-product-card">
      <Link
        to={`/store/products/${product.id}`}
        className="store-product-visual"
        aria-label={`View ${product.name}`}
      >
        <span aria-hidden="true">{productInitials(product.name)}</span>
      </Link>
      <div className="store-product-body">
        <p className="store-product-sku">{product.sku}</p>
        <h2>
          <Link to={`/store/products/${product.id}`}>{product.name}</Link>
        </h2>
        {product.description && (
          <p className="store-product-description">{product.description}</p>
        )}
        <div className="store-product-footer">
          <div>
            <p className="store-price">{formatMoney(product.price_cents, product.currency)}</p>
            <p className={`store-stock${product.quantity_available === 0 ? ' out' : ''}`}>
              {product.quantity_available === 0
                ? 'Out of stock'
                : `${product.quantity_available} available`}
            </p>
          </div>
          <button
            type="button"
            className="button button-primary button-small"
            onClick={() => onAdd(product)}
            disabled={product.quantity_available === 0}
            aria-label={`Add ${product.name} to cart`}
          >
            <PlusIcon /> Add
          </button>
        </div>
      </div>
    </article>
  )
}

export function StoreProductsPage() {
  const { add, itemCount } = useCart()
  const [data, setData] = useState<ProductList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{ message: string; requestId: string | null } | null>(
    null,
  )
  const [reload, setReload] = useState(0)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    api
      .listProducts({ page_size: 100 })
      .then((result) => {
        if (active) setData(result)
      })
      .catch((caught: unknown) => {
        if (!active) return
        setError({
          message: errorMessage(caught),
          requestId: isApiError(caught) ? caught.requestId : null,
        })
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [reload])

  const retry = () => {
    setLoading(true)
    setError(null)
    setReload((value) => value + 1)
  }

  const handleAdd = (product: Product) => {
    add(product)
    setNotice(`${product.name} added to your cart.`)
  }

  return (
    <div className="store-stack">
      <section className="store-hero">
        <div className="store-hero-copy">
          <p className="store-eyebrow">Forge goods</p>
          <h1 className="store-title">Objects for focused work.</h1>
          <p className="store-description">
            A small collection of durable desk essentials. Browse the catalog, build a
            cart, and reserve your order. Payment is not connected in this phase.
          </p>
          <div className="store-hero-actions">
            <Link className="button button-primary" to="/store/cart">
              <CartIcon /> View cart
              {itemCount > 0 && <span className="button-count">{itemCount}</span>}
            </Link>
            <button
              type="button"
              className="button button-secondary"
              onClick={retry}
              disabled={loading}
            >
              <RefreshIcon /> Refresh
            </button>
          </div>
        </div>
        <div className="store-hero-mark" aria-hidden="true">
          <span>F</span>
          <p>Built for the everyday</p>
        </div>
      </section>

      {notice && (
        <p className="store-notice" role="status">
          {notice}{' '}
          <Link className="text-link" to="/store/cart">
            Go to cart <ArrowRightIcon />
          </Link>
        </p>
      )}

      {error && (
        <ErrorBanner
          message={error.message}
          requestId={error.requestId}
          onRetry={retry}
        />
      )}

      {loading ? (
        <div className="store-product-grid" role="status" aria-label="Loading products">
          {Array.from({ length: 6 }, (_, index) => (
            <div className="store-product-card store-product-skeleton" key={index}>
              <span className="skeleton store-skeleton-visual" />
              <span className="skeleton skeleton-wide" />
              <span className="skeleton skeleton-short" />
            </div>
          ))}
        </div>
      ) : data && data.items.length === 0 ? (
        <EmptyState
          title="The shelves are empty"
          description="No products are available yet. Seed the inventory service and refresh."
          action={
            <button
              type="button"
              className="button button-primary button-small"
              onClick={retry}
            >
              <RefreshIcon /> Refresh catalog
            </button>
          }
        />
      ) : (
        <section aria-labelledby="store-products-heading">
          <div className="store-section-heading">
            <div>
              <h2 id="store-products-heading">The collection</h2>
              <p>{data?.total ?? 0} products available</p>
            </div>
            <Link className="text-link" to="/store/cart">
              Review cart <ArrowRightIcon />
            </Link>
          </div>
          <div className="store-product-grid">
            {data?.items.map((product) => (
              <StoreProductCard key={product.id} product={product} onAdd={handleAdd} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
