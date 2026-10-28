import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useHealth } from '../hooks/useHealth'
import {
  DashboardIcon,
  OrdersIcon,
  PlusIcon,
  ProductsIcon,
  StoreIcon,
} from './Icons'

const HEALTH_LABELS = {
  checking: 'Checking API',
  online: 'API connected',
  offline: 'API unreachable',
}

export function Layout() {
  const health = useHealth()
  const { pathname } = useLocation()
  const ordersActive =
    pathname === '/orders' ||
    (pathname.startsWith('/orders/') && pathname !== '/orders/new')

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            F
          </div>
          <div>
            <p className="brand-name">Forge</p>
            <p className="brand-subtitle">Commerce Ops</p>
          </div>
        </div>

        <nav className="nav" aria-label="Primary navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <DashboardIcon />
            <span>Overview</span>
          </NavLink>
          <Link
            to="/orders"
            className={`nav-link${ordersActive ? ' active' : ''}`}
            aria-current={ordersActive ? 'page' : undefined}
          >
            <OrdersIcon />
            <span>Orders</span>
          </Link>
          <NavLink
            to="/products"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <ProductsIcon />
            <span>Inventory</span>
          </NavLink>
          <Link to="/store" className="nav-link">
            <StoreIcon />
            <span>Open storefront</span>
          </Link>
          <NavLink
            to="/orders/new"
            className={({ isActive }) => `nav-link nav-link-accent${isActive ? ' active' : ''}`}
          >
            <PlusIcon />
            <span>New order</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <p className="sidebar-label">Environment</p>
          <p className="environment-chip">Local development</p>
          <p className="sidebar-note">
            Orders and inventory are served by the Forge microservices.
          </p>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-title">
            <span className="topbar-kicker">Operations console</span>
            <span className="topbar-divider" aria-hidden="true" />
            <span className="topbar-context">Forge Commerce</span>
          </div>
          <div className={`health-pill health-${health}`} role="status" aria-live="polite">
            <span className="health-dot" aria-hidden="true" />
            {HEALTH_LABELS[health]}
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
