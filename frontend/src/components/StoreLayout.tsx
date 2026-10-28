import { Link, NavLink, Outlet } from 'react-router-dom'
import { CartIcon } from './Icons'
import { useCart } from '../store/cartState'

export function StoreLayout() {
  const { itemCount } = useCart()

  return (
    <div className="store-shell">
      <header className="store-header">
        <Link className="store-brand" to="/store" aria-label="Forge storefront home">
          <span className="store-brand-mark" aria-hidden="true">
            F
          </span>
          <span>
            <strong>Forge</strong>
            <small>Everyday goods</small>
          </span>
        </Link>

        <nav className="store-nav" aria-label="Storefront navigation">
          <NavLink
            to="/store"
            end
            className={({ isActive }) => `store-nav-link${isActive ? ' active' : ''}`}
          >
            Shop
          </NavLink>
          <NavLink
            to="/store/cart"
            className={({ isActive }) => `store-nav-link store-cart-link${isActive ? ' active' : ''}`}
          >
            <CartIcon />
            <span>Cart</span>
            <span className="cart-count" aria-label={`${itemCount} items in cart`}>
              {itemCount}
            </span>
          </NavLink>
        </nav>
      </header>

      <main className="store-content">
        <Outlet />
      </main>

      <footer className="store-footer">
        <span>Forge Commerce</span>
        <span>Local demo storefront · Payment is not connected</span>
      </footer>
    </div>
  )
}
