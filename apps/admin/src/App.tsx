import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Route, Routes } from 'react-router-dom'
import { Nav } from './components/Nav'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AuthProvider } from './context/AuthContext'
import { CustomersPage } from './pages/Customers'
import { DashboardPage } from './pages/Dashboard'
import { LoginPage } from './pages/Login'
import { OrdersPage } from './pages/Orders'
import { PricingPage } from './pages/Pricing'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1 } },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route
              path="/*"
              element={
                <>
                  <Nav />
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/customers" element={<CustomersPage />} />
                    <Route path="/orders" element={<OrdersPage />} />
                    <Route path="/pricing" element={<PricingPage />} />
                  </Routes>
                </>
              }
            />
          </Route>
        </Routes>
      </AuthProvider>
    </QueryClientProvider>
  )
}
