import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, errorMessage, isApiError } from '../api/client'
import type { Product, ProductList } from '../api/types'
import { EmptyState, ErrorBanner, InlineSpinner, TableSkeleton } from '../components/Feedback'
import { ArrowLeftIcon, PlusIcon } from '../components/Icons'
import { PageHeader } from '../components/PageHeader'
import { formatMoney } from '../lib/format'

interface DraftLine {
  id: string
  productId: string
  quantity: number
}

type Errors = Record<string, string>

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function newLine(): DraftLine {
  return {
    id: crypto.randomUUID(),
    productId: '',
    quantity: 1,
  }
}

function extractOrderId(details: unknown): string | null {
  if (
    details &&
    typeof details === 'object' &&
    'order_id' in details &&
    typeof (details as { order_id: unknown }).order_id === 'string'
  ) {
    return (details as { order_id: string }).order_id
  }
  return null
}

export function NewOrderPage() {
  const navigate = useNavigate()
  const idempotencyKey = useRef<string | null>(null)

  const [products, setProducts] = useState<ProductList | null>(null)
  const [loadingProducts, setLoadingProducts] = useState(true)
  const [catalogError, setCatalogError] = useState<{
    message: string
    requestId: string | null
  } | null>(null)

  const [customer, setCustomer] = useState({ name: '', email: '' })
  const [lines, setLines] = useState<DraftLine[]>(() => [newLine()])
  const [errors, setErrors] = useState<Errors>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<{
    message: string
    requestId: string | null
    orderId: string | null
  } | null>(null)

  useEffect(() => {
    let active = true
    api
      .listProducts({ page_size: 100 })
      .then((result) => {
        if (active) setProducts(result)
      })
      .catch((caught: unknown) => {
        if (!active) return
        setCatalogError({
          message: errorMessage(caught),
          requestId: isApiError(caught) ? caught.requestId : null,
        })
      })
      .finally(() => {
        if (active) setLoadingProducts(false)
      })

    return () => {
      active = false
    }
  }, [])

  const markDirty = () => {
    idempotencyKey.current = null
    setSubmitError(null)
  }

  const updateCustomer = (field: 'name' | 'email', value: string) => {
    markDirty()
    setCustomer((current) => ({ ...current, [field]: value }))
  }

  const updateLine = (lineId: string, patch: Partial<DraftLine>) => {
    markDirty()
    setLines((current) =>
      current.map((line) => (line.id === lineId ? { ...line, ...patch } : line)),
    )
  }

  const addLine = () => {
    if (lines.length >= 50) return
    markDirty()
    setLines((current) => [...current, newLine()])
  }

  const removeLine = (lineId: string) => {
    markDirty()
    setLines((current) => current.filter((line) => line.id !== lineId))
  }

  const validate = (): Errors => {
    const next: Errors = {}
    if (!customer.name.trim()) {
      next.customerName = 'Enter the customer name.'
    }
    if (!EMAIL_PATTERN.test(customer.email.trim())) {
      next.customerEmail = 'Enter a valid email address.'
    }
    if (lines.length === 0) {
      next.items = 'Add at least one product.'
    }

    const seen = new Set<string>()
    for (const line of lines) {
      if (!line.productId) {
        next[`product-${line.id}`] = 'Select a product.'
      } else if (seen.has(line.productId)) {
        next.items = 'Each product can only appear once.'
      } else {
        seen.add(line.productId)
      }
      if (!Number.isInteger(line.quantity) || line.quantity < 1 || line.quantity > 100) {
        next[`quantity-${line.id}`] = 'Quantity must be between 1 and 100.'
      }
    }
    return next
  }

  const estimatedTotal = useMemo(() => {
    if (!products) return 0
    return lines.reduce((total, line) => {
      const product = products.items.find((item) => item.id === line.productId)
      return total + (product?.price_cents ?? 0) * line.quantity
    }, 0)
  }, [lines, products])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validation = validate()
    setErrors(validation)
    if (Object.keys(validation).length > 0) return

    const key = idempotencyKey.current ?? crypto.randomUUID()
    idempotencyKey.current = key
    setSubmitting(true)
    setSubmitError(null)

    try {
      const order = await api.createOrder(
        {
          customer: {
            name: customer.name.trim(),
            email: customer.email.trim(),
          },
          items: lines.map((line) => ({
            product_id: line.productId,
            quantity: line.quantity,
          })),
        },
        key,
      )
      navigate(`/orders/${order.id}`, { state: { justCreated: true } })
    } catch (caught: unknown) {
      setSubmitError({
        message: errorMessage(caught),
        requestId: isApiError(caught) ? caught.requestId : null,
        orderId: isApiError(caught) ? extractOrderId(caught.details) : null,
      })
    } finally {
      setSubmitting(false)
    }
  }

  const catalogProducts: Product[] = products?.items ?? []

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Order management"
        title="Create order"
        description="The order is persisted as pending, then inventory is reserved through the internal inventory service."
        actions={
          <Link className="button button-secondary" to="/orders">
            <ArrowLeftIcon /> Back to orders
          </Link>
        }
      />

      {catalogError && (
        <ErrorBanner message={catalogError.message} requestId={catalogError.requestId} />
      )}

      {submitError && (
        <div className="stack stack-tight">
          <ErrorBanner
            message={submitError.message}
            requestId={submitError.requestId}
          />
          {submitError.orderId && (
            <p className="inline-note">
              The order was retained for audit.{" "}
              <Link className="text-link" to={`/orders/${submitError.orderId}`}>
                View order {submitError.orderId.slice(0, 8).toUpperCase()}
              </Link>
            </p>
          )}
        </div>
      )}

      {loadingProducts ? (
        <TableSkeleton rows={4} />
      ) : catalogProducts.length === 0 ? (
        <EmptyState
          title="No products available"
          description="Seed the inventory service before creating orders."
        />
      ) : (
        <form onSubmit={handleSubmit} noValidate>
          <div className="order-form-layout">
            <div className="stack">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Customer</h2>
                    <p>Contact details attached to this order.</p>
                  </div>
                </div>
                <div className="form-grid">
                  <label className="field">
                    <span>Customer name</span>
                    <input
                      type="text"
                      value={customer.name}
                      onChange={(event) => updateCustomer('name', event.target.value)}
                      placeholder="Ada Lovelace"
                      autoComplete="name"
                      aria-invalid={Boolean(errors.customerName)}
                    />
                    {errors.customerName && (
                      <span className="field-error">{errors.customerName}</span>
                    )}
                  </label>
                  <label className="field">
                    <span>Email address</span>
                    <input
                      type="email"
                      value={customer.email}
                      onChange={(event) => updateCustomer('email', event.target.value)}
                      placeholder="ada@example.com"
                      autoComplete="email"
                      aria-invalid={Boolean(errors.customerEmail)}
                    />
                    {errors.customerEmail && (
                      <span className="field-error">{errors.customerEmail}</span>
                    )}
                  </label>
                </div>
              </section>

              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Order items</h2>
                    <p>Stock is checked atomically when the order is submitted.</p>
                  </div>
                  <button
                    type="button"
                    className="button button-secondary button-small"
                    onClick={addLine}
                    disabled={lines.length >= 50}
                  >
                    <PlusIcon /> Add line
                  </button>
                </div>

                {errors.items && <p className="field-error">{errors.items}</p>}

                <div className="line-items">
                  {lines.map((line, index) => {
                    const product = catalogProducts.find(
                      (item) => item.id === line.productId,
                    )
                    const insufficient =
                      product !== undefined && line.quantity > product.quantity_available
                    return (
                      <div className="line-item" key={line.id}>
                        <div className="line-number" aria-hidden="true">
                          {index + 1}
                        </div>
                        <label className="field">
                          <span>Product</span>
                          <select
                            value={line.productId}
                            onChange={(event) =>
                              updateLine(line.id, { productId: event.target.value })
                            }
                            aria-invalid={Boolean(errors[`product-${line.id}`])}
                          >
                            <option value="">Select a product</option>
                            {catalogProducts.map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.name} · {item.quantity_available} available
                              </option>
                            ))}
                          </select>
                          {errors[`product-${line.id}`] && (
                            <span className="field-error">
                              {errors[`product-${line.id}`]}
                            </span>
                          )}
                        </label>
                        <label className="field field-quantity">
                          <span>Quantity</span>
                          <input
                            type="number"
                            min={1}
                            max={100}
                            value={line.quantity}
                            onChange={(event) =>
                              updateLine(line.id, {
                                quantity: Number(event.target.value),
                              })
                            }
                            aria-invalid={Boolean(errors[`quantity-${line.id}`])}
                          />
                          {errors[`quantity-${line.id}`] && (
                            <span className="field-error">
                              {errors[`quantity-${line.id}`]}
                            </span>
                          )}
                        </label>
                        <button
                          type="button"
                          className="button button-ghost button-small line-remove"
                          onClick={() => removeLine(line.id)}
                          aria-label={`Remove line ${index + 1}`}
                        >
                          Remove
                        </button>
                        {insufficient && (
                          <p className="line-warning">
                            Only {product.quantity_available} available. The order will be
                            rejected if stock cannot be reserved.
                          </p>
                        )}
                      </div>
                    )
                  })}
                </div>
              </section>
            </div>

            <aside className="panel summary-panel">
              <div className="panel-heading">
                <div>
                  <h2>Summary</h2>
                  <p>Estimate before inventory confirmation.</p>
                </div>
              </div>
              <dl className="summary-list">
                <div>
                  <dt>Line items</dt>
                  <dd>{lines.length}</dd>
                </div>
                <div>
                  <dt>Estimated total</dt>
                  <dd className="summary-total">{formatMoney(estimatedTotal)}</dd>
                </div>
              </dl>
              <p className="summary-note">
                The final total and product snapshots are stored only after the inventory
                reservation succeeds.
              </p>
              <button
                type="submit"
                className="button button-primary button-block"
                disabled={submitting || loadingProducts}
              >
                {submitting ? (
                  <>
                    <InlineSpinner /> Reserving inventory
                  </>
                ) : (
                  'Create order'
                )}
              </button>
              <Link className="button button-ghost button-block" to="/orders">
                Cancel
              </Link>
            </aside>
          </div>
        </form>
      )}
    </div>
  )
}
