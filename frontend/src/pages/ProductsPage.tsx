import { useEffect, useState } from 'react'
import { api, errorMessage, isApiError } from '../api/client'
import type { ProductList } from '../api/types'
import { EmptyState, ErrorBanner, TableSkeleton } from '../components/Feedback'
import { RefreshIcon } from '../components/Icons'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { StockBadge } from '../components/StatusBadge'
import { formatMoney } from '../lib/format'

const PAGE_SIZE = 20

export function ProductsPage() {
  const [page, setPage] = useState(1)
  const [data, setData] = useState<ProductList | null>(null)
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
      .listProducts({ page, page_size: PAGE_SIZE })
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
  }, [page, reload])

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Catalog & stock"
        title="Inventory"
        description="Product stock is owned by the inventory service and proxied through the order service."
        actions={
          <button
            type="button"
            className="button button-secondary"
            onClick={() => setReload((value) => value + 1)}
            disabled={loading}
          >
            <RefreshIcon /> Refresh
          </button>
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
          <div>
            <h2>Product stock</h2>
            <p>Available units can be reserved by new orders.</p>
          </div>
          <p className="toolbar-meta">
            {data
              ? `${data.total} ${data.total === 1 ? 'product' : 'products'}`
              : 'Loading catalog'}
          </p>
        </div>

        {loading ? (
          <TableSkeleton rows={6} />
        ) : data && data.items.length === 0 ? (
          <EmptyState
            title="No products in the catalog"
            description="Seed the inventory service or create products through its internal API."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Product</th>
                    <th scope="col">SKU</th>
                    <th scope="col">Price</th>
                    <th scope="col">Available</th>
                    <th scope="col">Reserved</th>
                    <th scope="col">Stock state</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((product) => (
                    <tr key={product.id}>
                      <td>
                        <span className="cell-strong">{product.name}</span>
                        {product.description && (
                          <span className="cell-subtle">{product.description}</span>
                        )}
                      </td>
                      <td>
                        <code className="sku">{product.sku}</code>
                      </td>
                      <td>{formatMoney(product.price_cents, product.currency)}</td>
                      <td>
                        <span className="quantity-strong">{product.quantity_available}</span>
                      </td>
                      <td className="cell-muted">{product.quantity_reserved}</td>
                      <td>
                        <StockBadge available={product.quantity_available} />
                      </td>
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
                onPageChange={setPage}
              />
            )}
          </>
        )}
      </section>
    </div>
  )
}
