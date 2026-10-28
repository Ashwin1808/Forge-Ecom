import { Link } from 'react-router-dom'
import { ArrowLeftIcon } from '../components/Icons'

export function NotFoundPage() {
  return (
    <div className="panel not-found">
      <p className="eyebrow">404</p>
      <h1>Page not found</h1>
      <p>The requested console page does not exist.</p>
      <Link className="button button-primary" to="/">
        <ArrowLeftIcon /> Back to overview
      </Link>
    </div>
  )
}
