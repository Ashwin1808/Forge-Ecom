import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, errorMessage, isApiError } from '../api/client'
import type { Order } from '../api/types'
import { EmptyState, ErrorBanner, TableSkeleton } from '../components/Feedback'
import { ArrowLeftIcon, CartIcon, CheckIcon } from '../components/Icons'
import { PaymentBadge, StatusBadge } from '../components/StatusBadge'
import { formatDate, formatMoney, itemCount, shortId } from '../lib/format'

export function StoreOrderPage() {
  const { orderId } = useParams<{ orderId: string }>()
  const location = useLocation()
  const justCreated = Boolean(
    (location.state as { justCreated?: boolean } | null)?.justCreated,
  )
  const [order, setOrder] = useState<Order | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{ message: string; requestId: string | null } | null>(
    null,
  )
  const [reload, setReload] = useState(0)

  useEffect(() => {
    if (!orderId) return
    let active = true

    api
      .getStorefrontOrder(orderId)
      .then((result) => {
        if (active) setOrder(result)
      })
      .catch((caught: unknown) => {
        if (!active) return
        setError({
          message:
            isApiError(caught) && caught.status === 404
              ? 'Order not found.'
              : errorMessage(caught),
          requestId: isApiError(caught) ? caught.requestId : null,
        })
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [orderId, reload])

  const retry = () => {
    setLoading(true)
    setError(null)
    setReload((value) => value + 1)
  }

  if (loading && !order) {
    return (
      <div className="store-stack">
        <TableSkeleton rows={5} />
      </div>
    )
  }

  if (error && !order) {
    return (
      <div className="store-stack">
        <EmptyState
          title="Order not found"
          description={error.message}
          action={
            <Link className="button button-primary button-small" to="/store">
              <CartIcon /> Back to shop
            </Link>
          }
        />
      </div>
    )
  }

  if (!order) return null

  return (
    <div className="store-stack">
      <Link className="text-link store-back-link" to="/store">
        <ArrowLeftIcon /> Back to shop
      </Link>

      <div className="store-section-heading">
        <div>
          <p className="store-eyebrow">Order {shortId(order.id)}</p>
          <h1>
            {order.status === 'AWAITING_PAYMENT'
              ? 'Your order is reserved.'
              : order.status === 'CONFIRMED'
                ? 'Your order is confirmed.'
                : 'Order status'}
          </h1>
        </div>
        <div className="store-status-row">
          <StatusBadge status={order.status} />
          <PaymentBadge status={order.payment_status} />
        </div>
      </div>

      {error && (
        <ErrorBanner
          message={error.message}
          requestId={error.requestId}
          onRetry={retry}
        />
      )}

      {order.status === 'AWAITING_PAYMENT' && (
        <div className="alert alert-warning" role="status">
          <div className="alert-content">
            <strong>{justCreated ? 'Reservation created' : 'Awaiting payment'}</strong>
            <p>
              Your items are held
              {order.reservation_expires_at
                ? ` until ${formatDate(order.reservation_expires_at)}`
                : ''}
              . Payment is not connected in this phase, so no charge has been made.
            </p>
          </div>
        </div>
      )}

      {order.status === 'CONFIRMED' && (
        <div className="alert alert-success" role="status">
          <CheckIcon />
          <div className="alert-content">
            <strong>Order confirmed</strong>
            <p>Inventory was reserved and the order total was recorded.</p>
          </div>
        </div>
      )}

      {order.status === 'EXPIRED' && (
        <div className="alert alert-error" role="alert">
          <div className="alert-content">
            <strong>Reservation expired</strong>
            <p>
              The inventory hold was released because payment was not completed in time.
              Start a new checkout to try again.
            </p>
          </div>
        </div>
      )}

      {order.status === 'FAILED' && (
        <div className="alert alert-error" role="alert">
          <div className="alert-content">
            <strong>Order could not be reserved</strong>
            <p>{order.failure_message ?? 'The order could not be processed.'}</p>
          </div>
        </div>
      )}

      <div className="store-order-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Order details</h2>
              <p>Recorded when the reservation was created.</p>
            </div>
          </div>
          <dl className="detail-list">
            <div>
              <dt>Order ID</dt>
              <dd>
                <code>{order.id}</code>
              </dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDate(order.created_at)}</dd>
            </div>
            <div>
              <dt>Items</dt>
              <dd>
                {itemCount(order.items)} {itemCount(order.items) === 1 ? 'unit' : 'units'}
              </dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd className="summary-total">
                {formatMoney(order.total_cents, order.currency)}
              </dd>
            </div>
            <div>
              <dt>Reservation expires</dt>
              <dd>
                {order.reservation_expires_at
                  ? formatDate(order.reservation_expires_at)
                  : '—'}
              </dd>
            </div>
          </dl>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Delivery</h2>
              <p>Contact and address stored with this order.</p>
            </div>
          </div>
          <dl className="detail-list">
            <div>
              <dt>Name</dt>
              <dd>{order.customer.name}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{order.customer.email}</dd>
            </div>
            {order.delivery_address && (
              <>
                <div>
                  <dt>Address</dt>
                  <dd>
                    {order.delivery_address.line1}
                    {order.delivery_address.line2
                      ? `, ${order.delivery_address.line2}`
                      : ''}
                    <br />
                    {order.delivery_address.city}
                    {order.delivery_address.region
                      ? `, ${order.delivery_address.region}`
                      : ''}{' '}
                    {order.delivery_address.postal_code}
                    <br />
                    {order.delivery_address.country}
                  </dd>
                </div>
              </>
            )}
          </dl>
        </section>
      </div>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Items</h2>
            <p>Product details captured at reservation time.</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Product</th>
                <th scope="col">Quantity</th>
                <th scope="col">Unit price</th>
                <th scope="col">Line total</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item) => (
                <tr key={item.product_id}>
                  <td>
                    <span className="cell-strong">
                      {item.name ?? `Product ${item.product_id.slice(0, 8)}`}
                    </span>
                    <span className="cell-subtle">{item.sku ?? item.product_id}</span>
                  </td>
                  <td>{item.quantity}</td>
                  <td>{formatMoney(item.unit_price_cents, item.currency ?? order.currency)}</td>
                  <td>{formatMoney(item.line_total_cents, item.currency ?? order.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
