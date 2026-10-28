import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, errorMessage, isApiError } from '../api/client'
import type { Order } from '../api/types'
import { ErrorBanner, TableSkeleton } from '../components/Feedback'
import { ArrowLeftIcon, CheckIcon } from '../components/Icons'
import { PageHeader } from '../components/PageHeader'
import { PaymentBadge, StatusBadge } from '../components/StatusBadge'
import { formatDate, formatMoney, itemCount, shortId } from '../lib/format'

export function OrderDetailPage() {
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
      .getOrder(orderId)
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

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Order detail"
        title={order ? `Order ${shortId(order.id)}` : 'Order'}
        description="Authoritative order state, customer details, and inventory reservation outcome."
        actions={
          <Link className="button button-secondary" to="/orders">
            <ArrowLeftIcon /> Back to orders
          </Link>
        }
      />

      {justCreated && order?.status === 'CONFIRMED' && (
        <div className="alert alert-success" role="status">
          <CheckIcon />
          <div className="alert-content">
            <strong>Order confirmed</strong>
            <p>Inventory was reserved successfully and the order total was recorded.</p>
          </div>
        </div>
      )}

      {error && (
        <ErrorBanner
          message={error.message}
          requestId={error.requestId}
          onRetry={retry}
        />
      )}

      {loading && !order ? (
        <TableSkeleton rows={5} />
      ) : order ? (
        <>
          {order.status === 'FAILED' && (
            <div className="alert alert-error" role="alert">
              <div className="alert-content">
                <strong>Inventory reservation failed</strong>
                <p>{order.failure_message ?? 'The order could not be confirmed.'}</p>
                <p className="alert-meta">
                  Failure code: <code>{order.failure_code ?? 'unknown'}</code>
                </p>
                <p className="alert-meta">
                  The order remains in FAILED state for audit. This console does not retry
                  automatically.
                </p>
              </div>
            </div>
          )}

          {order.status === 'PENDING' && (
            <div className="alert alert-warning" role="status">
              <div className="alert-content">
                <strong>Order processing</strong>
                <p>
                  The order is persisted but inventory confirmation has not completed. It
                  may require reconciliation if it remains pending.
                </p>
              </div>
            </div>
          )}

          {order.status === 'AWAITING_PAYMENT' && (
            <div className="alert alert-warning" role="status">
              <div className="alert-content">
                <strong>Awaiting payment</strong>
                <p>
                  Inventory is reserved for this storefront order
                  {order.reservation_expires_at
                    ? ` until ${formatDate(order.reservation_expires_at)}`
                    : ''}
                  . Payment collection is not connected in this phase.
                </p>
              </div>
            </div>
          )}

          {order.status === 'EXPIRED' && (
            <div className="alert alert-error" role="alert">
              <div className="alert-content">
                <strong>Reservation expired</strong>
                <p>
                  {order.failure_message ??
                    'The inventory hold expired before payment was completed.'}
                </p>
                <p className="alert-meta">
                  Failure code: <code>{order.failure_code ?? 'reservation_expired'}</code>
                </p>
              </div>
            </div>
          )}

          <div className="detail-grid">
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Order summary</h2>
                  <p>Identifiers and commercial totals.</p>
                </div>
                <div className="badge-row">
                  <StatusBadge status={order.status} />
                  <PaymentBadge status={order.payment_status} />
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
                  <dt>Last updated</dt>
                  <dd>{formatDate(order.updated_at)}</dd>
                </div>
                <div>
                  <dt>Channel</dt>
                  <dd>{order.channel}</dd>
                </div>
                <div>
                  <dt>Payment</dt>
                  <dd>{order.payment_status ?? 'Not started'}</dd>
                </div>
                <div>
                  <dt>Items</dt>
                  <dd>
                    {itemCount(order.items)}{' '}
                    {itemCount(order.items) === 1 ? 'unit' : 'units'}
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
                <div>
                  <dt>Total</dt>
                  <dd className="summary-total">
                    {formatMoney(order.total_cents, order.currency)}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Customer</h2>
                  <p>Contact attached to this order.</p>
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
                <div>
                  <dt>Currency</dt>
                  <dd>{order.currency}</dd>
                </div>
                <div>
                  <dt>State</dt>
                  <dd>{order.status}</dd>
                </div>
                {order.delivery_address && (
                  <div>
                    <dt>Delivery</dt>
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
                )}
              </dl>
            </section>
          </div>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Order items</h2>
                <p>Product details are snapshotted when inventory confirms the order.</p>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Product</th>
                    <th scope="col">SKU</th>
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
                        <span className="cell-subtle">{item.product_id}</span>
                      </td>
                      <td>
                        <code className="sku">{item.sku ?? '—'}</code>
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
        </>
      ) : null}
    </div>
  )
}
