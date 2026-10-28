import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, errorMessage, isApiError } from '../api/client'
import type { OrderList, OrderStatus } from '../api/types'
import { EmptyState, ErrorBanner, TableSkeleton } from '../components/Feedback'
import { PlusIcon, RefreshIcon } from '../components/Icons'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { StatusBadge } from '../components/StatusBadge'
import { formatDate, formatMoney, itemCount, shortId } from '../lib/format'

const STATUSES: Array<{ value: '' | OrderStatus; label: string }> = [
  { value: '', label: 'All statuses' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'CONFIRMED', label: 'Confirmed' },
  { value: 'FAILED', label: 'Failed' },
]

const PAGE_SIZE = 20

function parseStatus(value: string | null): '' | OrderStatus {
  if (value === 'PENDING' || value === 'CONFIRMED' || value === 'FAILED') {
    return value
  }
  return ''
}

export function OrdersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1)
  const status = parseStatus(searchParams.get('status'))

  const [data, setData] = useState<OrderList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{ message: string; requestId: string | null } | null>(
    null,
  )
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    api
      .listOrders({
        page,
        page_size: PAGE_SIZE,
        status: status || undefined,
      })
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
  }, [page, status, reload])

  const updateFilters = (nextStatus: string, nextPage = 1) => {
    const params = new URLSearchParams()
    if (nextStatus) params.set('status', nextStatus)
    if (nextPage > 1) params.set('page', String(nextPage))
    setSearchParams(params)
  }

  const showEmpty = !loading && data && data.items.length === 0

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Order management"
        title="Orders"
        description="Every order records its inventory reservation outcome. Failed orders remain visible for audit."
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

      <section className="panel">
        <div className="toolbar">
          <label className="field field-inline">
            <span>Filter by status</span>
            <select
              value={status}
              onChange={(event) => updateFilters(event.target.value)}
            >
              {STATUSES.map((option) => (
                <option key={option.value || 'all'} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <p className="toolbar-meta">
            {data
              ? `${data.total} ${data.total === 1 ? 'order' : 'orders'}`
              : 'Loading orders'}
          </p>
        </div>

        {loading ? (
          <TableSkeleton rows={6} />
        ) : showEmpty ? (
          <EmptyState
            title={status ? `No ${status.toLowerCase()} orders` : 'No orders yet'}
            description={
              status
                ? 'Try a different status filter or create a new order.'
                : 'Orders created through the console will appear here with their reservation outcome.'
            }
            action={
              <Link className="button button-primary button-small" to="/orders/new">
                <PlusIcon /> Create order
              </Link>
            }
          />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Order</th>
                    <th scope="col">Customer</th>
                    <th scope="col">Items</th>
                    <th scope="col">Total</th>
                    <th scope="col">Status</th>
                    <th scope="col">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((order) => (
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
                      <td className="cell-muted">{formatDate(order.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data && (
              <Pagination
                page={data.page}
                pageSize={data.page_size}
                total={data.total}
                onPageChange={(nextPage) => updateFilters(status, nextPage)}
              />
            )}
          </>
        )}
      </section>
    </div>
  )
}
