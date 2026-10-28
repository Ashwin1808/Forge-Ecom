import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api/client'
import {
  CONFIRMED_ORDER,
  PRODUCT_LAMP,
  PRODUCT_NOTEBOOK,
  makeProductList,
} from '../test/fixtures'
import { NewOrderPage } from './NewOrderPage'

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/orders/new']}>
      <Routes>
        <Route path="/orders/new" element={<NewOrderPage />} />
        <Route path="/orders/:orderId" element={<div>Order detail stub</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

async function fillValidOrder() {
  await screen.findByRole('option', { name: /Aurora Desk Lamp/ })
  await userEvent.type(screen.getByLabelText('Customer name'), 'Ada Lovelace')
  await userEvent.type(screen.getByLabelText('Email address'), 'ada@example.com')
  await userEvent.selectOptions(screen.getByLabelText('Product'), PRODUCT_LAMP.id)
  await userEvent.clear(screen.getByLabelText('Quantity'))
  await userEvent.type(screen.getByLabelText('Quantity'), '2')
}

describe('NewOrderPage', () => {
  beforeEach(() => {
    vi.spyOn(api, 'listProducts').mockResolvedValue(
      makeProductList([PRODUCT_LAMP, PRODUCT_NOTEBOOK]),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('validates required customer fields before submitting', async () => {
    const createOrder = vi.spyOn(api, 'createOrder')
    renderPage()

    await screen.findByRole('option', { name: /Aurora Desk Lamp/ })
    await userEvent.click(screen.getByRole('button', { name: 'Create order' }))

    expect(screen.getByText('Enter the customer name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Select a product.')).toBeInTheDocument()
    expect(createOrder).not.toHaveBeenCalled()
  })

  it('submits the order with an idempotency key and navigates to the detail page', async () => {
    const createOrder = vi.spyOn(api, 'createOrder').mockResolvedValue(CONFIRMED_ORDER)
    renderPage()

    await fillValidOrder()
    await userEvent.click(screen.getByRole('button', { name: 'Create order' }))

    expect(await screen.findByText('Order detail stub')).toBeInTheDocument()
    expect(createOrder).toHaveBeenCalledTimes(1)

    const [payload, idempotencyKey] = createOrder.mock.calls[0]
    expect(payload).toEqual({
      customer: { name: 'Ada Lovelace', email: 'ada@example.com' },
      items: [{ product_id: PRODUCT_LAMP.id, quantity: 2 }],
    })
    expect(idempotencyKey).toMatch(/^[A-Za-z0-9._:-]{8,128}$/)
  })

  it('shows a retained failed order when inventory rejects the reservation', async () => {
    const failedOrderId = '55555555-5555-4555-8555-555555555555'
    vi.spyOn(api, 'createOrder').mockRejectedValue(
      new ApiError(
        409,
        'insufficient_inventory',
        'Insufficient inventory for Aurora Desk Lamp.',
        'req-123',
        { order_id: failedOrderId },
      ),
    )
    renderPage()

    await fillValidOrder()
    await userEvent.click(screen.getByRole('button', { name: 'Create order' }))

    expect(
      await screen.findByText('Insufficient inventory for Aurora Desk Lamp.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/req-123/)).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /View order 55555555/i }),
    ).toHaveAttribute('href', `/orders/${failedOrderId}`)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Create order' })).toBeEnabled()
    })
  })
})
