import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { PRODUCT_LAMP } from '../test/fixtures'
import { CartProvider } from '../store/CartProvider'
import { StoreCartPage } from './StoreCartPage'

function seedCart(quantity = 2) {
  localStorage.setItem(
    'forge-store-cart-v1',
    JSON.stringify([
      {
        productId: PRODUCT_LAMP.id,
        sku: PRODUCT_LAMP.sku,
        name: PRODUCT_LAMP.name,
        priceCents: PRODUCT_LAMP.price_cents,
        currency: PRODUCT_LAMP.currency,
        quantity,
        quantityAvailable: PRODUCT_LAMP.quantity_available,
      },
    ]),
  )
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/store/cart']}>
      <CartProvider>
        <StoreCartPage />
      </CartProvider>
    </MemoryRouter>,
  )
}

describe('StoreCartPage', () => {
  beforeEach(() => {
    seedCart()
  })

  it('renders cart lines and updates quantity and totals', async () => {
    renderPage()

    expect(screen.getByText('Aurora Desk Lamp')).toBeInTheDocument()
    expect(screen.getByText('2 items')).toBeInTheDocument()
    expect(screen.getAllByText('$258.00')).toHaveLength(2)

    const quantity = screen.getByLabelText('Quantity for Aurora Desk Lamp')
    fireEvent.change(quantity, { target: { value: '3' } })

    expect(screen.getByText('3 items')).toBeInTheDocument()
    expect(screen.getAllByText('$387.00')).toHaveLength(2)
  })

  it('removes an item and shows the empty state', async () => {
    renderPage()

    await userEvent.click(
      screen.getByRole('button', { name: 'Remove Aurora Desk Lamp from cart' }),
    )

    expect(screen.getByText('Your cart is empty')).toBeInTheDocument()
    expect(screen.queryByText('Aurora Desk Lamp')).not.toBeInTheDocument()
  })

  it('links to checkout when the cart has items', () => {
    renderPage()

    expect(screen.getByRole('link', { name: /Continue to checkout/ })).toHaveAttribute(
      'href',
      '/store/checkout',
    )
  })
})
