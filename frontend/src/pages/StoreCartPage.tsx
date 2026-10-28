import { Link } from 'react-router-dom'
import { EmptyState } from '../components/Feedback'
import { ArrowRightIcon, CartIcon, TrashIcon } from '../components/Icons'
import { formatMoney } from '../lib/format'
import { useCart } from '../store/cartState'

export function StoreCartPage() {
  const { items, itemCount, subtotalCents, currency, updateQuantity, remove, clear } =
    useCart()

  if (items.length === 0) {
    return (
      <div className="store-stack">
        <div className="store-section-heading">
          <div>
            <p className="store-eyebrow">Your cart</p>
            <h1>Nothing here yet.</h1>
          </div>
        </div>
        <EmptyState
          title="Your cart is empty"
          description="Browse the collection and add a few considered essentials."
          action={
            <Link className="button button-primary button-small" to="/store">
              <CartIcon /> Browse products
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="store-stack">
      <div className="store-section-heading">
        <div>
          <p className="store-eyebrow">Your cart</p>
          <h1>
            {itemCount} {itemCount === 1 ? 'item' : 'items'}
          </h1>
        </div>
        <button type="button" className="button button-ghost button-small" onClick={clear}>
          Clear cart
        </button>
      </div>

      <div className="store-cart-layout">
        <section className="store-cart-list" aria-label="Cart items">
          {items.map((item) => (
            <article className="store-cart-item" key={item.productId}>
              <Link
                className="store-cart-visual"
                to={`/store/products/${item.productId}`}
                aria-label={`View ${item.name}`}
              >
                {item.name.slice(0, 1).toUpperCase()}
              </Link>
              <div className="store-cart-body">
                <div>
                  <p className="store-product-sku">{item.sku}</p>
                  <h2>
                    <Link to={`/store/products/${item.productId}`}>{item.name}</Link>
                  </h2>
                  <p className="store-cart-unit">
                    {formatMoney(item.priceCents, item.currency)} each
                  </p>
                </div>
                <div className="store-cart-controls">
                  <label className="store-quantity store-quantity-compact">
                    <span>Quantity</span>
                    <input
                      type="number"
                      min={1}
                      max={item.quantityAvailable}
                      value={item.quantity}
                      onChange={(event) =>
                        updateQuantity(item.productId, Number(event.target.value))
                      }
                      onFocus={(event) => event.currentTarget.select()}
                      aria-label={`Quantity for ${item.name}`}
                    />
                  </label>
                  <p className="store-cart-line-total">
                    {formatMoney(item.priceCents * item.quantity, item.currency)}
                  </p>
                  <button
                    type="button"
                    className="button button-ghost button-small"
                    onClick={() => remove(item.productId)}
                    aria-label={`Remove ${item.name} from cart`}
                  >
                    <TrashIcon /> Remove
                  </button>
                </div>
              </div>
            </article>
          ))}
        </section>

        <aside className="store-summary panel" aria-label="Order summary">
          <div className="panel-heading">
            <div>
              <h2>Summary</h2>
              <p>Inventory is checked when you reserve the order.</p>
            </div>
          </div>
          <dl className="summary-list">
            <div>
              <dt>Items</dt>
              <dd>{itemCount}</dd>
            </div>
            <div>
              <dt>Subtotal</dt>
              <dd className="summary-total">{formatMoney(subtotalCents, currency)}</dd>
            </div>
          </dl>
          <p className="summary-note">
            No payment is collected in this phase. The order will be held as awaiting
            payment until the reservation expires.
          </p>
          <Link className="button button-primary button-block" to="/store/checkout">
            Continue to checkout <ArrowRightIcon />
          </Link>
          <Link className="button button-ghost button-block" to="/store">
            Keep shopping
          </Link>
        </aside>
      </div>
    </div>
  )
}
