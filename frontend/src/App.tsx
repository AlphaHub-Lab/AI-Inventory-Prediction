import { lazy, Suspense, useEffect, useState } from 'react'
import Layout, { type PageKey } from './components/Layout'
import { api, clearSession } from './lib/api'
import type { User } from './types'
import LoginPage from './pages/LoginPage'
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const AdminDashboardPage = lazy(() => import('./pages/AdminDashboardPage'))
const ProductsPage = lazy(() => import('./pages/ProductsPage'))
const DataPage = lazy(() => import('./pages/DataPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const DataInputPage = lazy(() => import('./pages/DataInputPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))
const CheckoutPage = lazy(() => import('./pages/CheckoutPage'))
const ReorderPage = lazy(() => import('./pages/ReorderPage'))
const ReceiptsPage = lazy(() => import('./pages/ReceiptsPage'))

import ErrorBoundary from './components/ErrorBoundary'
import LoadingState from './components/LoadingState'

const VALID_PAGES: PageKey[] = [
  'dashboard', 'data-input', 'products', 'inventory', 'checkout', 'sales', 'receipts', 'forecasts',
  'waste', 'reorders', 'orders', 'suppliers', 'analytics',
  'chat', 'knowledge', 'models', 'admin', 'users', 'settings'
]

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [page, setPageState] = useState<PageKey>(() => {
    const hash = window.location.hash.replace(/^#\/?/, '') as PageKey
    return VALID_PAGES.includes(hash) ? hash : 'dashboard'
  })
  const [checking, setChecking] = useState(true)

  const setPage = (newPage: PageKey) => {
    setPageState(newPage)
    window.location.hash = newPage
  }

  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash.replace(/^#\/?/, '') as PageKey
      if (VALID_PAGES.includes(hash)) {
        setPageState(hash)
      }
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    // Real-time cookie session authentication check on startup
    api<User>('/api/auth/me')
      .then(setUser)
      .catch(() => {
        clearSession()
        setUser(null)
      })
      .finally(() => setChecking(false))
  }, [])

  const logout = () => {
    void api('/api/auth/logout', { method: 'POST' }).catch(() => {})
    clearSession()
    sessionStorage.removeItem('inventory_checkout_cart')
    setUser(null)
    setPage('dashboard')
  }

  if (checking) return <LoadingState className="boot-screen" label="Connecting securely to Stockwise AI…" />
  if (!user) return <LoginPage onLogin={setUser}/>

  const activePage = user.role === 'admin'
    ? (page === 'admin' || page === 'settings' ? page : 'dashboard')
    : (page === 'admin' ? 'dashboard' : page)
  let view: React.ReactNode
  if (activePage === 'dashboard' && user.role === 'admin') view = <AdminDashboardPage onNavigate={setPage}/>
  else if (activePage === 'dashboard') view = <DashboardPage onNavigate={setPage}/>
  else if (activePage === 'admin' && user.role === 'admin') view = <AdminPage currentUser={user}/>
  else if (activePage === 'data-input') view = <DataInputPage/>
  else if (activePage === 'products') view = <ProductsPage/>
  else if (activePage === 'checkout') view = <CheckoutPage/>
  else if (activePage === 'reorders') view = <ReorderPage currentUser={user}/>
  else if (activePage === 'receipts') view = <ReceiptsPage currentUser={user}/>
  else if (activePage === 'chat') view = <ChatPage/>
  else view = <DataPage kind={activePage} currentUser={user}/>

  return (
    <Layout page={activePage} setPage={setPage} user={user} onLogout={logout}>
      <ErrorBoundary>
        <Suspense fallback={<LoadingState label="Loading workspace…" />}>
          {view}
        </Suspense>
      </ErrorBoundary>
    </Layout>
  )
}

export default App
