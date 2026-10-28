import { Link } from 'react-router-dom'
import { ArrowLeftIcon } from '../components/Icons'

export function StoreNotFoundPage() {
  return (
    <div className="panel not-found">
      <p className="eyebrow">404</p>
      <h1>Page not found</h1>
      <p>The requested storefront page does not exist.</p>
      <Link className="button button-primary" to="/store">
        <ArrowLeftIcon /> Back to shop
      </Link>
    </div>
  )
}
