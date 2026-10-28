import type { ReactNode } from 'react'
import { AlertIcon, RefreshIcon } from './Icons'

export function ErrorBanner({
  message,
  requestId,
  onRetry,
}: {
  message: string
  requestId?: string | null
  onRetry?: () => void
}) {
  return (
    <div className="alert alert-error" role="alert">
      <AlertIcon />
      <div className="alert-content">
        <strong>Request failed</strong>
        <p>{message}</p>
        {requestId && (
          <p className="alert-meta">
            Request reference: <code>{requestId}</code>
          </p>
        )}
      </div>
      {onRetry && (
        <button type="button" className="button button-secondary button-small" onClick={onRetry}>
          <RefreshIcon /> Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="empty-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  )
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="skeleton-table" aria-label="Loading data" role="status">
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index}>
          <span className="skeleton skeleton-wide" />
          <span className="skeleton" />
          <span className="skeleton" />
          <span className="skeleton skeleton-short" />
        </div>
      ))}
    </div>
  )
}

export function InlineSpinner() {
  return <span className="spinner" aria-hidden="true" />
}
