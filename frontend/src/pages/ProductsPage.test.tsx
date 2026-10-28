import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import {
  PRODUCT_LAMP,
  PRODUCT_NOTEBOOK,
  makeProductList,
} from '../test/fixtures'
import { ProductsPage } from './ProductsPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <ProductsPage />
    </MemoryRouter>,
  )
}

describe('ProductsPage', () => {
  beforeEach(() => {
    vi.spyOn(api, 'listProducts').mockResolvedValue(
      makeProductList([PRODUCT_LAMP, PRODUCT_NOTEBOOK]),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders inventory with prices and stock states', async () => {
    renderPage()

    expect(await screen.findByText('Aurora Desk Lamp')).toBeInTheDocument()
    expect(screen.getByText('Foundry Notebook')).toBeInTheDocument()
    expect(screen.getByText('LAMP-001')).toBeInTheDocument()
    expect(screen.getByText('$129.00')).toBeInTheDocument()
    expect(screen.getByText('In stock')).toBeInTheDocument()
    expect(screen.getByText('Low stock')).toBeInTheDocument()
    expect(screen.getByText('2 products')).toBeInTheDocument()
  })

  it('shows an empty state when the catalog has no products', async () => {
    vi.mocked(api.listProducts).mockResolvedValue(makeProductList([], 0))
    renderPage()

    expect(await screen.findByText('No products in the catalog')).toBeInTheDocument()
  })
})
