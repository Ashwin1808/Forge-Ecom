import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage, isApiError } from '../api/client'
import type { OrderList, ProductList } from '../api/types'
import { EmptyState, ErrorBanner, TableSkeleton } from '../components/Feedback'
import { ArrowRightIcon, PlusIcon, RefreshIcon } from '../components/Icons'
import { PageHeader } from '../components/PageHeader'
import { PaymentBadge, StatusBadge } from '../components/StatusBadge'
import { formatDate, formatMoney, itemCount, shortId } from '../lib/format'

interface DashboardData {
  total: number
  confirmed: number
  failed: number
  pending: number
  awaiting: number
  expired: number
  recent: OrderList
  products: ProductList
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{ message: string; requestId: string | null } | null>(
    null,
  )
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    Promise.all([
      api.listOrders({ page_size: 1 }),
      api.listOrders({ page_size: 1, status: 'CONFIRMED' }),
      api.listOrders({ page_size: 1, status: 'FAILED' }),
      api.listOrders({ page_size: 1, status: 'AWAITING_PAYMENT' }),
      api.listOrders({ page_size: 1, status: 'EXPIRED' }),
      api.listOrders({ page_size: 6 }),
      api.listProducts({ page_size: 100 }),
    ])
      .then(([total, confirmed, failed, awaiting, expired, recent, products]) => {
        if (!active) return
        setData({
          total: total.total,
          confirmed: confirmed.total,
          failed: failed.total,
          awaiting: awaiting.total,
          expired: expired.total,
          pending: Math.max(
            0,
            total.total -
              confirmed.total -
              failed.total -
              awaiting.total -
              expired.total,
          ),
          recent,
          products,
        })
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

  const lowStock = data
    ? data.products.items
        .filter((product) => product.quantity_available <= 10)
        .sort((a, b) => a.quantity_available - b.quantity_available)
        .slice(0, 5)
    : []

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Operations overview"
        title="Commerce at a glance"
        description="Monitor order flow, confirmation health, and inventory pressure across Forge Commerce."
        actions={
          <>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setReload((value) => value + 1)}
              disabled={loading}
            >
              <RefreshIcon /> Refresh
            </button>
            <Link className="button button-primary" to="/orders/new">
              <PlusIcon /> Create order
            </Link>
          </>
        }
      />

      {error && (
        <ErrorBanner
          message={error.message}
          requestId={error.requestId}
          onRetry={() => setReload((value) => value + 1)}
        />
      )}

      {loading && !data ? (
        <TableSkeleton rows={6} />
      ) : (
        <>
          <section className="metric-grid" aria-label="Order and inventory metrics">
            <article className="metric-card">
              <span className="metric-label">Total orders</span>
              <p className="metric-value">{data?.total ?? 0}</p>
              <p className="metric-foot">All order states</p>
            </article>
            <article className="metric-card metric-card-warning">
              <span className="metric-label">Awaiting payment</span>
              <p className="metric-value">{data?.awaiting ?? 0}</p>
              <p className="metric-foot">Reservations held</p>
            </article>
            <article className="metric-card metric-card-positive">
              <span className="metric-label">Confirmed</span>
              <p className="metric-value">{data?.confirmed ?? 0}</p>
              <p className="metric-foot">Inventory reserved</p>
            </article>
            <article className="metric-card metric-card-negative">
              <span className="metric-label">Failed</span>
              <p className="metric-value">{data?.failed ?? 0}</p>
              <p className="metric-foot">Needs review</p>
            </article>
            <article className="metric-card metric-card-expired">
              <span className="metric-label">Expired</span>
              <p className="metric-value">{data?.expired ?? 0}</p>
              <p className="metric-foot">Reservations released</p>
            </article>
          </section>

          <div className="dashboard-grid">
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Recent orders</h2>
                  <p>Latest activity from the order service.</p>
                </div>
                <Link className="text-link" to="/orders">
                  View all <ArrowRightIcon />
                </Link>
              </div>
              {data && data.recent.items.length === 0 ? (
                <EmptyState
                  title="No orders yet"
                  description="Create the first order to exercise the inventory reservation workflow."
                  action={
                    <Link className="button button-primary button-small" to="/orders/new">
                      <PlusIcon /> Create order
                    </Link>
                  }
                />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Order</th>
                        <th scope="col">Customer</th>
                        <th scope="col">Items</th>
                        <th scope="col">Total</th>
                        <th scope="col">Status</th>
                        <th scope="col">Payment</th>
                        <th scope="col">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data?.recent.items.map((order) => (
                        <tr key={order.id}>
                          <td>
                            <Link className="order-link" to={`/orders/${order.id}`}>
                              {shortId(order.id)}
                            </Link>
                          </td>
                          <td>
                            <span className="cell-strong">{order.customer.name}</span>
                            <span className="cell-subtle">{order.customer.email}</span>
                          </td>
                          <td>{itemCount(order.items)}</td>
                          <td>{formatMoney(order.total_cents, order.currency)}</td>
                          <td>
                            <StatusBadge status={order.status} />
                          </td>
                          <td>
                            <PaymentBadge status={order.payment_status} />
                          </td>
                          <td className="cell-muted">{formatDate(order.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="panel stock-panel">
              <div className="panel-heading">
                <div>
                  <h2>Stock watchlist</h2>
                  <p>Products that need replenishment attention.</p>
                </div>
                <Link className="text-link" to="/products">
                  Inventory <ArrowRightIcon />
                </Link>
              </div>
              {lowStock.length === 0 ? (
                <EmptyState
                  title="Stock looks healthy"
                  description="No products are at or below the low-stock threshold."
                />
              ) : (
                <ul className="stock-list">
                  {lowStock.map((product) => (
                    <li key={product.id}>
                      <div>
                        <p className="cell-strong">{product.name}</p>
                        <p className="cell-subtle">{product.sku}</p>
                      </div>
                      <div className="stock-quantity">
                        <strong>{product.quantity_available}</strong>
                        <span>available</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <div className="dashboard-note">
                <strong>{data?.pending ?? 0}</strong> order
                {(data?.pending ?? 0) === 1 ? '' : 's'} currently pending confirmation.
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  )
}
