import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function Nav() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <nav style={{ background: '#1976d2', color: '#fff', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 24, height: 48 }}>
      <strong>Wise-Wash</strong>
      {[
        { to: '/', label: 'Dashboard' },
        { to: '/customers', label: 'Customers' },
        { to: '/orders', label: 'Orders' },
        { to: '/pricing', label: 'Pricing' },
      ].map(({ to, label }) => (
        <Link key={to} to={to} style={{ color: '#fff', textDecoration: 'none' }}>{label}</Link>
      ))}
      <button
        onClick={handleLogout}
        style={{ marginLeft: 'auto', background: 'transparent', color: '#fff', border: '1px solid #fff', borderRadius: 4, padding: '4px 12px', cursor: 'pointer' }}
      >
        Sign out
      </button>
    </nav>
  )
}
