import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { api, ApiError } from '../api/client'
import { PRODUCT_LAMP, PRODUCT_NOTEBOOK, makeProductList } from '../test/fixtures'
import { CartProvider } from '../store/CartProvider'
import { useCart } from '../store/cartState'
import { StoreProductsPage } from './StoreProductsPage'

function CartProbe() {
  const { itemCount } = useCart()
  return <span data-testid="cart-count">{itemCount}</span>
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/store']}>
      <CartProvider>
        <StoreProductsPage />
        <CartProbe />
      </CartProvider>
    </MemoryRouter>,
  )
}

describe('StoreProductsPage', () => {
  beforeEach(() => {
    vi.spyOn(api, 'listProducts').mockResolvedValue(
      makeProductList([PRODUCT_LAMP, PRODUCT_NOTEBOOK]),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the storefront product grid and adds an item to the cart', async () => {
    renderPage()

    expect(await screen.findByText('Aurora Desk Lamp')).toBeInTheDocument()
    expect(screen.getByText('Foundry Notebook')).toBeInTheDocument()
    expect(screen.getByText('$129.00')).toBeInTheDocument()
    expect(screen.getByText('12 available')).toBeInTheDocument()

    await userEvent.click(
      screen.getByRole('button', { name: 'Add Aurora Desk Lamp to cart' }),
    )

    expect(screen.getByTestId('cart-count')).toHaveTextContent('1')
    await waitFor(() => {
      expect(localStorage.getItem('forge-store-cart-v1')).toContain(PRODUCT_LAMP.id)
    })
  })

  it('shows a loading state while the catalog is pending', () => {
    vi.mocked(api.listProducts).mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByRole('status', { name: 'Loading products' })).toBeInTheDocument()
  })

  it('shows an empty state when no products are available', async () => {
    vi.mocked(api.listProducts).mockResolvedValue(makeProductList([]))
    renderPage()

    expect(await screen.findByText('The shelves are empty')).toBeInTheDocument()
  })

  it('shows an error state when the catalog fails', async () => {
    vi.mocked(api.listProducts).mockRejectedValue(
      new ApiError(503, 'catalog_unavailable', 'Catalog is unavailable.', 'req-42'),
    )
    renderPage()

    expect(await screen.findByText('Catalog is unavailable.')).toBeInTheDocument()
    expect(screen.getByText(/req-42/)).toBeInTheDocument()
  })

  it('routes /store to the storefront without operations navigation', async () => {
    render(
      <MemoryRouter initialEntries={['/store']}>
        <CartProvider>
          <App />
        </CartProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByText('Objects for focused work.')).toBeInTheDocument()
    expect(screen.queryByText('Operations console')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Shop' })).toBeInTheDocument()
  })
})
