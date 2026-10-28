import { ArrowLeftIcon, ArrowRightIcon } from './Icons'

interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  return (
    <div className="pagination">
      <p className="pagination-summary">
        Showing <strong>{start}</strong>–<strong>{end}</strong> of <strong>{total}</strong>
      </p>
      <div className="pagination-controls">
        <button
          type="button"
          className="button button-secondary button-small"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          <ArrowLeftIcon /> Previous
        </button>
        <span className="pagination-page">
          Page {page} of {pages}
        </span>
        <button
          type="button"
          className="button button-secondary button-small"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          aria-label="Next page"
        >
          Next <ArrowRightIcon />
        </button>
      </div>
    </div>
  )
}
