import type { OrderStatus, PaymentStatus } from '../api/types'

const LABELS: Record<OrderStatus, string> = {
  PENDING: 'Pending',
  AWAITING_PAYMENT: 'Awaiting payment',
  CONFIRMED: 'Confirmed',
  FAILED: 'Failed',
  EXPIRED: 'Expired',
}

const CLASSES: Record<OrderStatus, string> = {
  PENDING: 'pending',
  AWAITING_PAYMENT: 'awaiting',
  CONFIRMED: 'confirmed',
  FAILED: 'failed',
  EXPIRED: 'expired',
}

const PAYMENT_LABELS: Record<PaymentStatus, string> = {
  CREATED: 'Created',
  PENDING: 'Pending',
  PAID: 'Paid',
  FAILED: 'Failed',
  REFUNDED: 'Refunded',
}

const PAYMENT_CLASSES: Record<PaymentStatus, string> = {
  CREATED: 'created',
  PENDING: 'pending',
  PAID: 'paid',
  FAILED: 'failed',
  REFUNDED: 'refunded',
}

export function StatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={`badge badge-${CLASSES[status]}`}>
      <span className="badge-dot" aria-hidden="true" />
      {LABELS[status]}
    </span>
  )
}

export function PaymentBadge({ status }: { status: PaymentStatus | null }) {
  if (!status) {
    return <span className="badge badge-payment-none">Not started</span>
  }
  return (
    <span className={`badge badge-payment-${PAYMENT_CLASSES[status]}`}>
      <span className="badge-dot" aria-hidden="true" />
      {PAYMENT_LABELS[status]}
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
