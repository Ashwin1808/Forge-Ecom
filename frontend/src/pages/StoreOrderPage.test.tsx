import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { AWAITING_ORDER } from '../test/fixtures'
import { CartProvider } from '../store/CartProvider'
import { StoreOrderPage } from './StoreOrderPage'

function renderPage(orderId = AWAITING_ORDER.id) {
  return render(
    <MemoryRouter initialEntries={[`/store/orders/${orderId}`]}>
      <CartProvider>
        <Routes>
          <Route path="/store/orders/:orderId" element={<StoreOrderPage />} />
        </Routes>
      </CartProvider>
    </MemoryRouter>,
  )
}

describe('StoreOrderPage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows the reservation hold without claiming a successful payment', async () => {
    vi.spyOn(api, 'getStorefrontOrder').mockResolvedValue(AWAITING_ORDER)
    renderPage()

    expect(await screen.findByText('Your order is reserved.')).toBeInTheDocument()
    expect(screen.getByText(/Payment is not connected/)).toBeInTheDocument()
    expect(screen.getByText(/no charge has been made/)).toBeInTheDocument()
    expect(screen.getAllByText('Awaiting payment').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Created').length).toBeGreaterThan(0)
    expect(screen.getByText(/1 Market Street/)).toBeInTheDocument()
    expect(screen.queryByText(/paid successfully/i)).not.toBeInTheDocument()
  })

  it('shows the expired state and released reservation message', async () => {
    vi.spyOn(api, 'getStorefrontOrder').mockResolvedValue({
      ...AWAITING_ORDER,
      status: 'EXPIRED',
      failure_code: 'reservation_expired',
      failure_message: 'The checkout reservation expired before payment was completed.',
    })
    renderPage()

    expect(await screen.findByText('Reservation expired')).toBeInTheDocument()
    expect(screen.getAllByText('Reservation expired').length).toBeGreaterThan(0)
    expect(screen.getByText(/inventory hold was released/)).toBeInTheDocument()
  })
})
