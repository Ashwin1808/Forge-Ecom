import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api/client'
import { AWAITING_ORDER, PRODUCT_LAMP } from '../test/fixtures'
import { CartProvider } from '../store/CartProvider'
import { useCart } from '../store/cartState'
import { StoreCheckoutPage } from './StoreCheckoutPage'

function CartProbe() {
  const { itemCount } = useCart()
  return <span data-testid="cart-count">{itemCount}</span>
}

function seedCart() {
  localStorage.setItem(
    'forge-store-cart-v1',
    JSON.stringify([
      {
        productId: PRODUCT_LAMP.id,
        sku: PRODUCT_LAMP.sku,
        name: PRODUCT_LAMP.name,
        priceCents: PRODUCT_LAMP.price_cents,
        currency: PRODUCT_LAMP.currency,
        quantity: 1,
        quantityAvailable: PRODUCT_LAMP.quantity_available,
      },
    ]),
  )
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/store/checkout']}>
      <CartProvider>
        <Routes>
          <Route path="/store/checkout" element={<StoreCheckoutPage />} />
          <Route path="/store/orders/:orderId" element={<div>Store order stub</div>} />
        </Routes>
        <CartProbe />
      </CartProvider>
    </MemoryRouter>,
  )
}

async function fillCheckout() {
  await userEvent.type(screen.getByLabelText('Full name'), 'Grace Hopper')
  await userEvent.type(screen.getByLabelText('Email address'), 'grace@example.com')
  await userEvent.type(screen.getByLabelText('Street address'), '1 Market Street')
  await userEvent.type(screen.getByLabelText('Apartment, suite, etc. (optional)'), 'Suite 200')
  await userEvent.type(screen.getByLabelText('City'), 'San Francisco')
  await userEvent.type(screen.getByLabelText('State / region (optional)'), 'CA')
  await userEvent.type(screen.getByLabelText('Postal code'), '94105')
}

describe('StoreCheckoutPage', () => {
  beforeEach(() => {
    seedCart()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('validates required checkout fields before submitting', async () => {
    const createCheckout = vi.spyOn(api, 'createCheckout')
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: 'Reserve order' }))

    expect(screen.getByText('Enter your name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter the street address.')).toBeInTheDocument()
    expect(createCheckout).not.toHaveBeenCalled()
  })

  it('submits an idempotent checkout and clears the cart on success', async () => {
    const createCheckout = vi
      .spyOn(api, 'createCheckout')
      .mockResolvedValue(AWAITING_ORDER)
    renderPage()

    await fillCheckout()
    await userEvent.click(screen.getByRole('button', { name: 'Reserve order' }))

    expect(await screen.findByText('Store order stub')).toBeInTheDocument()
    expect(createCheckout).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('cart-count')).toHaveTextContent('0')

    const [payload, idempotencyKey] = createCheckout.mock.calls[0]
    expect(payload).toEqual({
      customer: { name: 'Grace Hopper', email: 'grace@example.com' },
      delivery_address: {
        line1: '1 Market Street',
        line2: 'Suite 200',
        city: 'San Francisco',
        region: 'CA',
        postal_code: '94105',
        country: 'US',
      },
      items: [{ product_id: PRODUCT_LAMP.id, quantity: 1 }],
    })
    expect(idempotencyKey).toMatch(/^[A-Za-z0-9._:-]{8,128}$/)
  })

  it('uses a fresh idempotency key after an expired checkout', async () => {
    const createCheckout = vi
      .spyOn(api, 'createCheckout')
      .mockRejectedValueOnce(
        new ApiError(
          409,
          'checkout_expired',
          'This checkout reservation expired. Start a new checkout.',
          'req-expired',
          { order_id: AWAITING_ORDER.id },
        ),
      )
      .mockResolvedValueOnce(AWAITING_ORDER)
    renderPage()

    await fillCheckout()
    await userEvent.click(screen.getByRole('button', { name: 'Reserve order' }))
    expect(
      await screen.findByText('This checkout reservation expired. Start a new checkout.'),
    ).toBeInTheDocument()
    const firstKey = createCheckout.mock.calls[0][1]

    await userEvent.click(screen.getByRole('button', { name: 'Reserve order' }))
    expect(await screen.findByText('Store order stub')).toBeInTheDocument()
    const secondKey = createCheckout.mock.calls[1][1]
    expect(secondKey).not.toBe(firstKey)
  })

  it('shows an inventory failure and links to the retained order', async () => {
    const orderId = '77777777-7777-4777-8777-777777777777'
    vi.spyOn(api, 'createCheckout').mockRejectedValue(
      new ApiError(
        409,
        'inventory_insufficient_stock',
        'One or more products do not have enough stock.',
        'req-checkout',
        { order_id: orderId },
      ),
    )
    renderPage()

    await fillCheckout()
    await userEvent.click(screen.getByRole('button', { name: 'Reserve order' }))

    expect(
      await screen.findByText('One or more products do not have enough stock.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/req-checkout/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /View order 77777777/i })).toHaveAttribute(
      'href',
      `/store/orders/${orderId}`,
    )
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Reserve order' })).toBeEnabled()
    })
  })
})
