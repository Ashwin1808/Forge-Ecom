import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import {
  CONFIRMED_ORDER,
  FAILED_ORDER,
  makeOrderList,
} from '../test/fixtures'
import { OrdersPage } from './OrdersPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <OrdersPage />
    </MemoryRouter>,
  )
}

describe('OrdersPage', () => {
  beforeEach(() => {
    vi.spyOn(api, 'listOrders').mockResolvedValue(
      makeOrderList([CONFIRMED_ORDER, FAILED_ORDER], 2),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders orders with customer, total, and status', async () => {
    renderPage()

    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()
    expect(screen.getByText('Grace Hopper')).toBeInTheDocument()
    expect(screen.getByText('$258.00')).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByText('Confirmed')).toBeInTheDocument()
    expect(within(table).getByText('Failed')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '33333333' })).toHaveAttribute(
      'href',
      `/orders/${CONFIRMED_ORDER.id}`,
    )
    expect(screen.getByText('2 orders')).toBeInTheDocument()
  })

  it('shows an empty state when there are no orders', async () => {
    vi.mocked(api.listOrders).mockResolvedValue(makeOrderList([], 0))
    renderPage()

    expect(await screen.findByText('No orders yet')).toBeInTheDocument()
    expect(screen.getByText('0 orders')).toBeInTheDocument()
  })

  it('requests a filtered list when the status filter changes', async () => {
    renderPage()
    await screen.findByText('Ada Lovelace')

    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'FAILED')

    await waitFor(() => {
      expect(api.listOrders).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        status: 'FAILED',
      })
    })
  })
})
