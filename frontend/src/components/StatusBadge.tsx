import type { OrderStatus } from '../api/types'

const LABELS: Record<OrderStatus, string> = {
  PENDING: 'Pending',
  CONFIRMED: 'Confirmed',
  FAILED: 'Failed',
}

export function StatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={`badge badge-${status.toLowerCase()}`}>
      <span className="badge-dot" aria-hidden="true" />
      {LABELS[status]}
    </span>
  )
}

export function StockBadge({ available }: { available: number }) {
  if (available === 0) {
    return <span className="badge badge-failed">Out of stock</span>
  }
  if (available <= 10) {
    return <span className="badge badge-warning">Low stock</span>
  }
  return <span className="badge badge-confirmed">In stock</span>
}
