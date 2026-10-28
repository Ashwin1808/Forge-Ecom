import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, errorMessage, isApiError } from '../api/client'
import { EmptyState, ErrorBanner, InlineSpinner } from '../components/Feedback'
import { ArrowLeftIcon, CartIcon } from '../components/Icons'
import { formatMoney } from '../lib/format'
import { useCart } from '../store/cartState'

interface CheckoutForm {
  name: string
  email: string
  line1: string
  line2: string
  city: string
  region: string
  postalCode: string
  country: string
}

type Errors = Partial<Record<keyof CheckoutForm, string>>

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const INITIAL_FORM: CheckoutForm = {
  name: '',
  email: '',
  line1: '',
  line2: '',
  city: '',
  region: '',
  postalCode: '',
  country: 'US',
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

export function StoreCheckoutPage() {
  const navigate = useNavigate()
  const { items, subtotalCents, currency, clear } = useCart()
  const idempotencyKey = useRef<string | null>(null)
  const [form, setForm] = useState<CheckoutForm>(INITIAL_FORM)
  const [errors, setErrors] = useState<Errors>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<{
    message: string
    requestId: string | null
    orderId: string | null
  } | null>(null)

  const markDirty = () => {
    idempotencyKey.current = null
    setSubmitError(null)
  }

  const updateField = (field: keyof CheckoutForm, value: string) => {
    markDirty()
    setForm((current) => ({ ...current, [field]: value }))
  }

  const validate = (): Errors => {
    const next: Errors = {}
    if (!form.name.trim()) next.name = 'Enter your name.'
    if (!EMAIL_PATTERN.test(form.email.trim())) {
      next.email = 'Enter a valid email address.'
    }
    if (!form.line1.trim()) next.line1 = 'Enter the street address.'
    if (!form.city.trim()) next.city = 'Enter the city.'
    if (!form.postalCode.trim()) next.postalCode = 'Enter the postal code.'
    if (form.country.trim().length < 2) next.country = 'Enter the country.'
    return next
  }

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
      const order = await api.createCheckout(
        {
          customer: {
            name: form.name.trim(),
            email: form.email.trim(),
          },
          delivery_address: {
            line1: form.line1.trim(),
            line2: form.line2.trim() || null,
            city: form.city.trim(),
            region: form.region.trim() || null,
            postal_code: form.postalCode.trim(),
            country: form.country.trim(),
          },
          items: items.map((item) => ({
            product_id: item.productId,
            quantity: item.quantity,
          })),
        },
        key,
      )
      clear()
      navigate(`/store/orders/${order.id}`, { state: { justCreated: true } })
    } catch (caught: unknown) {
      if (isApiError(caught) && caught.code === 'checkout_expired') {
        idempotencyKey.current = null
      }
      setSubmitError({
        message: errorMessage(caught),
        requestId: isApiError(caught) ? caught.requestId : null,
        orderId: isApiError(caught) ? extractOrderId(caught.details) : null,
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (items.length === 0) {
    return (
      <div className="store-stack">
        <EmptyState
          title="Your cart is empty"
          description="Add a product before starting checkout."
          action={
            <Link className="button button-primary button-small" to="/store">
              <CartIcon /> Browse products
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="store-stack">
      <Link className="text-link store-back-link" to="/store/cart">
        <ArrowLeftIcon /> Back to cart
      </Link>

      <div className="store-section-heading">
        <div>
          <p className="store-eyebrow">Checkout</p>
          <h1>Reserve your order.</h1>
          <p className="store-description">
            We will hold your items while the order waits for payment. No payment is
            collected in this phase.
          </p>
        </div>
      </div>

      {submitError && (
        <div className="store-stack store-stack-tight">
          <ErrorBanner
            message={submitError.message}
            requestId={submitError.requestId}
          />
          {submitError.orderId && (
            <p className="inline-note">
              The order was retained for audit.{' '}
              <Link className="text-link" to={`/store/orders/${submitError.orderId}`}>
                View order {submitError.orderId.slice(0, 8).toUpperCase()}
              </Link>
            </p>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="store-checkout-layout">
        <div className="store-stack">
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Contact</h2>
                <p>Where should we send the order confirmation?</p>
              </div>
            </div>
            <div className="form-grid">
              <label className="field">
                <span>Full name</span>
                <input
                  type="text"
                  value={form.name}
                  onChange={(event) => updateField('name', event.target.value)}
                  placeholder="Grace Hopper"
                  autoComplete="name"
                  aria-invalid={Boolean(errors.name)}
                />
                {errors.name && <span className="field-error">{errors.name}</span>}
              </label>
              <label className="field">
                <span>Email address</span>
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) => updateField('email', event.target.value)}
                  placeholder="grace@example.com"
                  autoComplete="email"
                  aria-invalid={Boolean(errors.email)}
                />
                {errors.email && <span className="field-error">{errors.email}</span>}
              </label>
            </div>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Delivery address</h2>
                <p>This address is stored with the order snapshot.</p>
              </div>
            </div>
            <div className="form-grid">
              <label className="field field-full">
                <span>Street address</span>
                <input
                  type="text"
                  value={form.line1}
                  onChange={(event) => updateField('line1', event.target.value)}
                  placeholder="1 Market Street"
                  autoComplete="address-line1"
                  aria-invalid={Boolean(errors.line1)}
                />
                {errors.line1 && <span className="field-error">{errors.line1}</span>}
              </label>
              <label className="field field-full">
                <span>Apartment, suite, etc. (optional)</span>
                <input
                  type="text"
                  value={form.line2}
                  onChange={(event) => updateField('line2', event.target.value)}
                  placeholder="Suite 200"
                  autoComplete="address-line2"
                />
              </label>
              <label className="field">
                <span>City</span>
                <input
                  type="text"
                  value={form.city}
                  onChange={(event) => updateField('city', event.target.value)}
                  placeholder="San Francisco"
                  autoComplete="address-level2"
                  aria-invalid={Boolean(errors.city)}
                />
                {errors.city && <span className="field-error">{errors.city}</span>}
              </label>
              <label className="field">
                <span>State / region (optional)</span>
                <input
                  type="text"
                  value={form.region}
                  onChange={(event) => updateField('region', event.target.value)}
                  placeholder="CA"
                  autoComplete="address-level1"
                />
              </label>
              <label className="field">
                <span>Postal code</span>
                <input
                  type="text"
                  value={form.postalCode}
                  onChange={(event) => updateField('postalCode', event.target.value)}
                  placeholder="94105"
                  autoComplete="postal-code"
                  aria-invalid={Boolean(errors.postalCode)}
                />
                {errors.postalCode && (
                  <span className="field-error">{errors.postalCode}</span>
                )}
              </label>
              <label className="field">
                <span>Country</span>
                <input
                  type="text"
                  value={form.country}
                  onChange={(event) => updateField('country', event.target.value)}
                  placeholder="US"
                  autoComplete="country"
                  aria-invalid={Boolean(errors.country)}
                />
                {errors.country && <span className="field-error">{errors.country}</span>}
              </label>
            </div>
          </section>
        </div>

        <aside className="panel store-summary">
          <div className="panel-heading">
            <div>
              <h2>Order summary</h2>
              <p>{items.length} product lines</p>
            </div>
          </div>
          <ul className="store-checkout-items">
            {items.map((item) => (
              <li key={item.productId}>
                <span>
                  {item.name} <small>× {item.quantity}</small>
                </span>
                <strong>
                  {formatMoney(item.priceCents * item.quantity, item.currency)}
                </strong>
              </li>
            ))}
          </ul>
          <dl className="summary-list">
            <div>
              <dt>Subtotal</dt>
              <dd className="summary-total">{formatMoney(subtotalCents, currency)}</dd>
            </div>
          </dl>
          <p className="summary-note">
            Submitting reserves inventory and creates an order awaiting payment. The
            reservation expires automatically if it is not paid.
          </p>
          <button
            type="submit"
            className="button button-primary button-block"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <InlineSpinner /> Reserving order
              </>
            ) : (
              'Reserve order'
            )}
          </button>
          <Link className="button button-ghost button-block" to="/store/cart">
            Back to cart
          </Link>
        </aside>
      </form>
    </div>
  )
}
