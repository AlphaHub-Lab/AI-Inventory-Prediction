import { BarChart3, Bot, Boxes, BrainCircuit, ClipboardList, FileText, LineChart, LogOut, Package, ShoppingCart, Truck, Users, Warehouse, FilePlus2, ShieldCheck, Receipt } from 'lucide-react'
import type { User } from '../types'

export type PageKey =
  | 'dashboard'
  | 'data-input'
  | 'products'
  | 'inventory'
  | 'checkout'
  | 'sales'
  | 'receipts'
  | 'reorders'
  | 'orders'
  | 'suppliers'
  | 'forecasts'
  | 'waste'
  | 'analytics'
  | 'chat'
  | 'knowledge'
  | 'models'
  | 'admin'
  | 'users'
  | 'settings'

interface NavLinkItem {
  key: PageKey
  label: string
  icon: typeof Boxes
  adminOnly?: boolean
  ownerOnly?: boolean
  generalAi?: boolean
  receiptAi?: boolean
}

const allLinks: NavLinkItem[] = [
  { key: 'dashboard', label: 'Overview', icon: BarChart3 },
  { key: 'products', label: 'Products & Master Catalog', icon: Package },
  { key: 'receipts', label: 'AI Receipt Scanner', icon: Receipt, receiptAi: true },
  { key: 'reorders', label: 'Reorder Replenishment', icon: ShoppingCart },
  { key: 'inventory', label: 'Inventory & Batches', icon: Warehouse },
  { key: 'checkout', label: 'POS Checkout', icon: ShoppingCart },
  { key: 'sales', label: 'Sales Activity', icon: LineChart },
  { key: 'orders', label: 'Purchase Orders', icon: FileText },
  { key: 'suppliers', label: 'Suppliers', icon: Truck },
  { key: 'data-input', label: 'Data Input Studio', icon: FilePlus2 },
  { key: 'forecasts', label: 'Demand Forecasting', icon: BrainCircuit, generalAi: true },
  { key: 'waste', label: 'Waste & Expiry Risk', icon: ClipboardList, generalAi: true },
  { key: 'analytics', label: 'What-If Simulation', icon: BarChart3, generalAi: true },
  { key: 'chat', label: 'AI Copilot Chat', icon: Bot, generalAi: true },
  { key: 'knowledge', label: 'Knowledge Base (RAG)', icon: FileText, generalAi: true },
  { key: 'models', label: 'Model Evaluation', icon: BrainCircuit, generalAi: true },
  { key: 'users', label: 'Associate Management', icon: Users, ownerOnly: true },
  { key: 'settings', label: 'System Settings', icon: Boxes },
  { key: 'admin', label: 'Administrator Portal', icon: ShieldCheck, adminOnly: true },
]

export default function Layout({
  page,
  setPage,
  user,
  onLogout,
  children
}: {
  page: PageKey
  setPage: (p: PageKey) => void
  user: User
  onLogout: () => void
  children: React.ReactNode
}) {
  const roleLabel =
    user.role === 'admin'
      ? 'Administrator'
      : user.role === 'business_owner'
      ? 'Business Owner'
      : 'Associate'

  // Determine allowed navigation links strictly according to RBAC
  const visibleLinks = allLinks.filter(link => {
    if (user.role === 'admin') {
      // Admin sees Global overview, Administrator Portal, Settings, or full portal
      return link.key === 'dashboard' || link.key === 'admin' || link.key === 'settings'
    }

    if (user.role === 'associate') {
      // ASSOCIATES MUST NOT SEE GENERAL AI
      if (link.generalAi) return false
      // ASSOCIATES CANNOT SEE ADMIN OR OWNER-ONLY USER MANAGEMENT
      if (link.adminOnly || link.ownerOnly || link.key === 'settings') return false

      // Receipt AI operational exception: allowed if user has receipt permissions
      if (link.receiptAi) {
        if (!user.permissions || user.permissions.length === 0) return true
        return user.permissions.some(p => p.startsWith('receipt.') || p === 'all')
      }

      return true
    }

    // Business Owner sees all business tools, receipt AI, general AI, and associate management
    if (link.adminOnly) return false
    return true
  }).map(link => {
    if (user.role === 'admin' && link.key === 'dashboard') {
      return { ...link, label: 'Global Overview' }
    }
    return link
  })

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">S</span>
          <span>
            Stockwise <b>AI</b>
          </span>
        </div>
        <nav>
          {visibleLinks.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              title={label}
              onClick={() => setPage(key)}
              className={page === key ? 'nav-link active' : 'nav-link'}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-user">
          <div className="avatar">{user.full_name ? user.full_name[0] : 'U'}</div>
          <div>
            <strong>{user.full_name}</strong>
            <small>{roleLabel}</small>
            {user.business_name && (
              <small className="sidebar-business">{user.business_name}</small>
            )}
          </div>
          <button aria-label="Log out" className="icon-button" onClick={onLogout} title="Sign Out">
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  )
}

