import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { StoreLayout } from './components/StoreLayout'
import { DashboardPage } from './pages/DashboardPage'
import { NewOrderPage } from './pages/NewOrderPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { OrderDetailPage } from './pages/OrderDetailPage'
import { OrdersPage } from './pages/OrdersPage'
import { ProductsPage } from './pages/ProductsPage'
import { StoreCartPage } from './pages/StoreCartPage'
import { StoreCheckoutPage } from './pages/StoreCheckoutPage'
import { StoreNotFoundPage } from './pages/StoreNotFoundPage'
import { StoreOrderPage } from './pages/StoreOrderPage'
import { StoreProductPage } from './pages/StoreProductPage'
import { StoreProductsPage } from './pages/StoreProductsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="orders/new" element={<NewOrderPage />} />
        <Route path="orders/:orderId" element={<OrderDetailPage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route path="store" element={<StoreLayout />}>
        <Route index element={<StoreProductsPage />} />
        <Route path="products/:productId" element={<StoreProductPage />} />
        <Route path="cart" element={<StoreCartPage />} />
        <Route path="checkout" element={<StoreCheckoutPage />} />
        <Route path="orders/:orderId" element={<StoreOrderPage />} />
        <Route path="*" element={<StoreNotFoundPage />} />
      </Route>
    </Routes>
  )
}
