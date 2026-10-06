import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Activity, Database, Download, RefreshCw, ShieldCheck, Trash2, UserPlus, Users } from 'lucide-react'
import { api } from '../lib/api'
import type { User } from '../types'
import LoadingState from '../components/LoadingState'

type Overview = { counts: Record<string, number>; active_accounts: number; sales_revenue: number; database_engine: string; database_bytes: number | null }
type Account = { id: number; email: string; full_name: string; role: User['role']; is_active: boolean; created_at: string; business_id: number | null; business_name: string | null; audit_events: number; inventory_movements: number; chat_conversations: number; purchase_orders: number }
type ActivityEvent = { id: number; actor: string; actor_email: string; action: string; entity: string; entity_id: string; details: Record<string, unknown>; created_at: string }
type BusinessRow = { id: number; name: string; business_type: string; master_database_name: string; local_database_name: string | null; owner_email: string; owner_phone?: string | null; owner_personal_email?: string | null; phone?: string | null; address?: string | null; is_active: boolean; created_at: string; accounts: number; products: number; sales: number }
type AlertRow = { id: string; severity: 'critical' | 'warning' | 'info'; business_id: number; business_name: string; kind: string; count: number }
type AdminTab = 'overview' | 'businesses' | 'accounts' | 'alerts' | 'activity'
type Draft = { role: User['role']; is_active: boolean; business_id: number | null }

const resources: [string, string][] = [
  ['businesses', 'Business workspaces'], ['products', 'Products'], ['sales', 'Sales transactions'], ['inventory_movements', 'Inventory movements'], ['batches', 'Inventory batches'],
  ['suppliers', 'Suppliers'], ['categories', 'Categories'], ['purchase_orders', 'Purchase orders'], ['purchase_order_items', 'Purchase order items'],
  ['forecasts', 'Forecast records'], ['reorder_recommendations', 'Reorder recommendations'], ['waste_predictions', 'Waste predictions'], ['expiry_alerts', 'Expiry alerts'],
  ['knowledge_documents', 'Knowledge documents'], ['knowledge_chunks', 'Knowledge chunks'], ['chat_conversations', 'Assistant conversations'], ['chat_messages', 'Assistant messages'], ['audit_events', 'Audit events'], ['model_runs', 'Model runs'],
]
function readableDate(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) }
function formatBytes(bytes: number | null) {
  if (bytes === null) return 'Unavailable'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']; let size = bytes / 1024; let unit = 0
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit++ }
  return `${size.toFixed(size < 10 ? 1 : 0)} ${units[unit]}`
}

export default function AdminPage({ currentUser }: { currentUser: User }) {
  const [tab, setTab] = useState<AdminTab>('overview')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [businesses, setBusinesses] = useState<BusinessRow[]>([])
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [drafts, setDrafts] = useState<Record<number, Draft>>({})
  const [query, setQuery] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showBusinessForm, setShowBusinessForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pageLoading, setPageLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [personalEmail, setPersonalEmail] = useState('')
  const [emailCode, setEmailCode] = useState('')
  const [emailCodeSent, setEmailCodeSent] = useState(false)
  const [verifiedPersonalEmail, setVerifiedPersonalEmail] = useState('')

  async function load() {
    setError('')
    try {
      const [summary, userRows, activityRows, businessRows, alertRows] = await Promise.all([
        api<Overview>('/api/admin/overview'), api<Account[]>('/api/admin/accounts'), api<ActivityEvent[]>('/api/admin/activity?limit=100'),
        api<BusinessRow[]>('/api/admin/businesses'), api<AlertRow[]>('/api/admin/notifications'),
      ])
      setOverview(summary); setAccounts(userRows); setEvents(activityRows); setBusinesses(businessRows); setAlerts(alertRows)
      setDrafts(Object.fromEntries(userRows.map(user => [user.id, { role: user.role, is_active: user.is_active, business_id: user.business_id }])))
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load administrator data.') }
    finally { setPageLoading(false) }
  }
  useEffect(() => { void load() }, [])

  const visibleAccounts = useMemo(() => accounts.filter(user => `${user.full_name} ${user.email} ${user.role}`.toLowerCase().includes(query.toLowerCase())), [accounts, query])

  async function createAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    const formElement = event.currentTarget; const form = new FormData(formElement)
    try {
      const role = String(form.get('role'))
      await api('/api/users', { method: 'POST', body: JSON.stringify({ full_name: String(form.get('full_name')).trim(), email: String(form.get('email')).trim(), password: String(form.get('password')), role, business_id: role === 'admin' ? null : Number(form.get('business_id')) }) })
      formElement.reset(); setShowCreate(false); setNotice('Account created.'); await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create account.') }
    finally { setBusy(false) }
  }

  async function saveAccount(account: Account) {
    const draft = drafts[account.id]
    if (!draft) return
    setBusy(true); setError(''); setNotice('')
    try {
      await api(`/api/admin/users/${account.id}`, { method: 'PUT', body: JSON.stringify(draft) })
      setNotice(`Access updated for ${account.full_name}.`); await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update account access.') }
    finally { setBusy(false) }
  }

  async function createBusiness(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    const formElement = event.currentTarget; const form = new FormData(formElement)
    try {
      if (personalEmail.trim().toLowerCase() !== verifiedPersonalEmail.toLowerCase() || !emailCode) throw new Error('Verify the owner personal email before creating this workspace.')
      await api('/api/admin/businesses', { method: 'POST', body: JSON.stringify({ name: String(form.get('business_name')).trim(), business_type: String(form.get('business_type')), owner_name: String(form.get('owner_name')).trim(), owner_email: String(form.get('owner_email')).trim(), owner_personal_email: personalEmail.trim(), owner_phone: String(form.get('owner_phone')).trim(), phone: String(form.get('business_phone')).trim(), address: String(form.get('business_address')).trim(), email_verification_code: emailCode, owner_password: String(form.get('owner_password')) }) })
      formElement.reset(); setShowBusinessForm(false); setNotice('Business workspace and owner account created.'); await load()
      setPersonalEmail(''); setEmailCode(''); setEmailCodeSent(false); setVerifiedPersonalEmail('')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create business workspace.') }
    finally { setBusy(false) }
  }

  async function sendOwnerCode() {
    if (!personalEmail.trim()) { setError('Enter the owner personal email first.'); return }
    setBusy(true); setError(''); setNotice('')
    try {
      await api('/api/admin/businesses/owner-email-code', { method: 'POST', body: JSON.stringify({ email: personalEmail.trim() }) })
      setEmailCodeSent(true); setVerifiedPersonalEmail(''); setNotice('Verification code sent to the owner personal email.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not send the email verification code.') }
    finally { setBusy(false) }
  }

  async function verifyOwnerCode() {
    setBusy(true); setError(''); setNotice('')
    try {
      await api('/api/admin/businesses/verify-owner-email', { method: 'POST', body: JSON.stringify({ email: personalEmail.trim(), code: emailCode }) })
      setVerifiedPersonalEmail(personalEmail.trim()); setNotice('Owner personal email verified.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not verify the email code.') }
    finally { setBusy(false) }
  }

  async function toggleBusiness(business: BusinessRow) {
    setBusy(true); setError(''); setNotice('')
    try {
      await api(`/api/admin/businesses/${business.id}`, { method: 'PUT', body: JSON.stringify({ is_active: !business.is_active }) })
      setNotice(`${business.name} ${business.is_active ? 'suspended' : 'reactivated'}.`); await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update workspace status.') }
    finally { setBusy(false) }
  }

  async function deleteBusiness(business: BusinessRow) {
    if (busy || !window.confirm(`Permanently delete ${business.name} and all of its accounts, inventory, sales, receipts, and operational history? This cannot be undone.`)) return
    setBusy(true); setError(''); setNotice('')
    try {
      await api(`/api/admin/businesses/${business.id}`, { method: 'DELETE' })
      setNotice(`${business.name} and its workspace data were permanently deleted.`); await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not delete the business workspace.') }
    finally { setBusy(false) }
  }

  async function setBusinessType(business: BusinessRow, business_type: string) {
    setBusy(true); setError(''); setNotice('')
    try {
      await api(`/api/admin/businesses/${business.id}`, { method: 'PUT', body: JSON.stringify({ is_active: business.is_active, business_type }) })
      setNotice(`${business.name} now uses the ${business_type} catalog mapping.`); await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update business type.') }
    finally { setBusy(false) }
  }

  async function deleteAccount(account: Account) {
    if (account.id === currentUser.id || busy) return
    const confirmed = window.confirm(`Permanently delete ${account.full_name} (${account.email})? Their sign-in, sessions, permissions, and assistant conversations will be deleted. Shared business inventory, orders, receipts, and audit history will remain, with this account detached from those records. This cannot be undone.`)
    if (!confirmed) return
    setBusy(true); setError(''); setNotice('')
    try {
      await api(`/api/admin/accounts/${account.id}`, { method: 'DELETE' })
      setAccounts(prev => prev.filter(row => row.id !== account.id))
      setDrafts(prev => { const next = { ...prev }; delete next[account.id]; return next })
      setNotice(`Account ${account.email} was permanently deleted.`); await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not delete account.') }
    finally { setBusy(false) }
  }

  function exportActivity() {
    const header = ['timestamp', 'actor', 'email', 'action', 'entity', 'entity_id', 'details']
    const rows = events.map(row => [row.created_at, row.actor, row.actor_email, row.action, row.entity, row.entity_id, JSON.stringify(row.details)])
    const csv = [header, ...rows].map(row => row.map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = 'stockwise-audit-activity.csv'; link.click(); URL.revokeObjectURL(url)
  }

  const totalRecords = overview ? Object.entries(overview.counts).filter(([key]) => key !== 'accounts').reduce((sum, [, count]) => sum + count, 0) : 0

  if (pageLoading) return <LoadingState label="Loading administrator workspace…" />

  return <div className="admin-page">
    <header className="page-header">
      <div><p className="eyebrow">CENTRAL ACCESS · CROSS-BUSINESS OVERSIGHT</p><h1>Super Administrator</h1><p>Oversee every business workspace, account, resource, and operational alert.</p></div>
      <div className="header-actions"><span className="admin-identity"><ShieldCheck size={15}/>{currentUser.email}</span><button className="secondary-button" onClick={() => { setBusy(true); void load().finally(() => setBusy(false)) }} disabled={busy}><RefreshCw size={15} className={busy ? 'animate-spin' : ''}/>Refresh</button></div>
    </header>
    {error && <div className="error-state" role="alert">{error}</div>}{notice && <div className="studio-notice" role="status">{notice}<button className="text-action" onClick={() => setNotice('')}>Dismiss</button></div>}
    {overview && <section className="admin-kpis">
      <article className="admin-stat"><span className="admin-stat-icon"><Users size={17}/></span><div><small>Business workspaces</small><strong>{overview.counts.businesses}</strong><span>{businesses.filter(b => b.is_active).length} active branches</span></div></article>
      <article className="admin-stat"><span className="admin-stat-icon mint"><ShieldCheck size={17}/></span><div><small>Active accounts</small><strong>{overview.active_accounts}</strong><span>{overview.counts.accounts} across all businesses</span></div></article>
      <article className="admin-stat"><span className="admin-stat-icon blue"><Database size={17}/></span><div><small>Records managed</small><strong>{totalRecords.toLocaleString()}</strong><span>Across {resources.length} resource types</span></div></article>
      <article className="admin-stat"><span className="admin-stat-icon orange"><Activity size={17}/></span><div><small>Recorded sales value</small><strong>₹{overview.sales_revenue.toLocaleString('en-IN')}</strong><span>{overview.counts.sales.toLocaleString()} transactions</span></div></article>
      <article className="admin-stat"><span className="admin-stat-icon"><Database size={17}/></span><div><small>Database footprint</small><strong>{formatBytes(overview.database_bytes)}</strong><span>{overview.database_engine.toUpperCase()}</span></div></article>
    </section>}
    <section className="admin-workspace">
      <div className="admin-tabs" role="tablist" aria-label="Administrator sections">
        {([['overview', 'Overview'], ['businesses', 'Businesses'], ['accounts', 'Accounts & access'], ['alerts', `Alerts${alerts.length ? ` · ${alerts.length}` : ''}`], ['activity', 'Audit log']] as [AdminTab, string][]).map(([key, label]) => <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? 'admin-tab active' : 'admin-tab'} onClick={() => setTab(key)}>{label}</button>)}
      </div>
      {tab === 'overview' && <div className="admin-section">
        <div className="admin-section-heading"><div><h2>Cross-business overview</h2><p>Central view of resources and activity across all business workspaces.</p></div><span className="admin-live"><i/>Live database</span></div>
        {overview && <div className="resource-grid">{resources.map(([key, label]) => <div className="resource-row" key={key}><span>{label}</span><strong>{(overview.counts[key] || 0).toLocaleString()}</strong></div>)}</div>}
        <div className="admin-footnote"><ShieldCheck size={15}/><span>Administrator data and account controls are restricted by server-side role checks.</span></div>
      </div>}
      {tab === 'businesses' && <div className="admin-section">
        <div className="admin-section-heading"><div><h2>Business workspaces</h2><p>Each business has a dedicated owner email and isolated operational data.</p></div><button className="primary-button" onClick={() => setShowBusinessForm(v => !v)}><UserPlus size={16}/>{showBusinessForm ? 'Close form' : 'Add business'}</button></div>
        {showBusinessForm && <form className="business-create-form" onSubmit={createBusiness}>
          <label>Business name<input name="business_name" required minLength={2} maxLength={180} placeholder="Northstar Pharmacy"/></label><label>Business type<select name="business_type" required><option value="medical">Medical store</option><option value="grocery">Grocery store</option><option value="restaurant">Restaurant / food business</option><option value="stationery">Stationery store</option><option value="dairy">Dairy store</option></select></label><label>Business mobile<input name="business_phone" type="tel" maxLength={40}/></label><label className="admin-wide-field">Business address<input name="business_address" maxLength={500}/></label><label>Owner name<input name="owner_name" required minLength={2} maxLength={120}/></label><label>Owner mobile number<input name="owner_phone" type="tel" required minLength={5} maxLength={40}/></label><label>Account email<input name="owner_email" type="email" required placeholder="owner@business.com"/></label><label>Owner personal email<input type="email" required value={personalEmail} onChange={e => { setPersonalEmail(e.target.value); setVerifiedPersonalEmail('') }} placeholder="personal@email.com"/><button type="button" className="row-action" disabled={busy || !personalEmail.trim()} onClick={() => void sendOwnerCode()}>{emailCodeSent ? 'Resend code' : 'Send verification code'}</button></label>{emailCodeSent && <label>Six-digit email code<input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={emailCode} onChange={e => setEmailCode(e.target.value.replace(/\D/g, '').slice(0, 6))}/><button type="button" className="row-action" disabled={busy || emailCode.length !== 6 || verifiedPersonalEmail.toLowerCase() === personalEmail.trim().toLowerCase()} onClick={() => void verifyOwnerCode()}>{verifiedPersonalEmail.toLowerCase() === personalEmail.trim().toLowerCase() ? 'Email verified' : 'Verify code'}</button></label>}<label>Temporary password<input name="owner_password" type="password" required minLength={12} maxLength={128} autoComplete="new-password"/><small>At least 12 characters with uppercase, lowercase, and a number.</small></label><button className="primary-button" disabled={busy || verifiedPersonalEmail.toLowerCase() !== personalEmail.trim().toLowerCase()}>Create workspace</button>
        </form>}
        <div className="table-wrap"><table className="admin-table business-table"><thead><tr><th>Business</th><th>Type / master catalog</th><th>Local database</th><th>Owner email</th><th>Accounts</th><th>Products</th><th>Sales</th><th>Status</th><th/></tr></thead><tbody>
          {businesses.map(business => <tr key={business.id}><td><strong>{business.name}</strong><small>Created {readableDate(business.created_at)}</small></td><td><select aria-label={`Business type for ${business.name}`} value={business.business_type} disabled={busy} onChange={event => void setBusinessType(business, event.target.value)}><option value="medical">Medical</option><option value="grocery">Grocery</option><option value="restaurant">Restaurant</option><option value="stationery">Stationery</option><option value="dairy">Dairy</option></select><small>{business.master_database_name}</small></td><td>{business.local_database_name || 'Not configured'}</td><td>{business.owner_email}<small>{business.owner_phone || 'Owner phone not provided'}</small><small>{business.phone || business.address || 'Business contact details not provided'}</small></td><td>{business.accounts}</td><td>{business.products}</td><td>{business.sales}</td><td><span className={business.is_active ? 'business-state active' : 'business-state disabled'}>{business.is_active ? 'Active' : 'Suspended'}</span></td><td><div className="admin-account-actions"><button className="row-action" disabled={busy} onClick={() => toggleBusiness(business)}>{business.is_active ? 'Suspend' : 'Reactivate'}</button><button className="row-action delete-account-action" disabled={busy} onClick={() => void deleteBusiness(business)} aria-label={`Delete business ${business.name}`}><Trash2 size={13}/><span>Delete</span></button></div></td></tr>)}
          {!businesses.length && <tr><td colSpan={9} className="empty-row">No business workspaces yet. Add a business to create its owner account.</td></tr>}
        </tbody></table></div>
      </div>}
      {tab === 'accounts' && <div className="admin-section">
        <div className="admin-section-heading"><div><h2>Accounts &amp; access</h2><p>Role assignments, account status, and activity by user.</p></div><button className="primary-button" onClick={() => setShowCreate(v => !v)}><UserPlus size={16}/>{showCreate ? 'Close form' : 'Add account'}</button></div>
        {showCreate && <form className="admin-create-form" onSubmit={createAccount}>
          <label>Full name<input name="full_name" required minLength={2} maxLength={120}/></label><label>Email<input name="email" type="email" required/></label><label>Temporary password<input name="password" type="password" required minLength={12} maxLength={128} autoComplete="new-password"/></label><label>Role<select name="role"><option value="associate">Associate</option><option value="admin">Administrator</option></select></label><label>Business<select name="business_id"><option value="">Not assigned</option>{businesses.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label><button className="primary-button" disabled={busy}>Create account</button>
        </form>}
        <div className="table-toolbar admin-toolbar"><label className="search"><Users size={15}/><input aria-label="Search accounts" placeholder="Search name, email, role" value={query} onChange={e => setQuery(e.target.value)}/></label><span>{visibleAccounts.length} accounts</span></div>
        <div className="table-wrap"><table className="admin-table"><thead><tr><th>Account</th><th>Business</th><th>Role</th><th>Activity</th><th>Stock moves</th><th>Assistant</th><th>Orders</th><th>Access</th><th>Actions</th></tr></thead><tbody>
          {visibleAccounts.map(account => { const draft = drafts[account.id] || { role: account.role, is_active: account.is_active, business_id: account.business_id }; const isSelf = account.id === currentUser.id; return <tr key={account.id}><td><strong>{account.full_name}</strong><small>{account.email}</small><small>Joined {readableDate(account.created_at)}</small></td><td><select aria-label={`Business for ${account.email}`} value={draft.business_id ?? ''} onChange={e => setDrafts(prev => ({ ...prev, [account.id]: { ...draft, business_id: e.target.value ? Number(e.target.value) : null } }))}><option value="">Central</option>{businesses.map(b => <option value={b.id} key={b.id}>{b.name}</option>)}</select></td><td><select aria-label={`Role for ${account.email}`} value={draft.role} onChange={e => setDrafts(prev => ({ ...prev, [account.id]: { ...draft, role: e.target.value as User['role'] } }))}><option value="associate">Associate</option><option value="business_owner">Business owner</option><option value="admin">Administrator</option></select></td><td>{account.audit_events}</td><td>{account.inventory_movements}</td><td>{account.chat_conversations}</td><td>{account.purchase_orders}</td><td><label className="access-toggle"><input type="checkbox" checked={draft.is_active} disabled={isSelf} onChange={e => setDrafts(prev => ({ ...prev, [account.id]: { ...draft, is_active: e.target.checked } }))}/><span>{draft.is_active ? 'Active' : 'Disabled'}</span></label></td><td><div className="admin-account-actions"><button className="row-action" disabled={busy || isSelf || (draft.role === account.role && draft.is_active === account.is_active && draft.business_id === account.business_id)} onClick={() => saveAccount(account)} title={isSelf ? 'Your own access cannot be changed here' : 'Save access changes'}>Save</button><button className="row-action delete-account-action" disabled={busy || isSelf} onClick={() => void deleteAccount(account)} title={isSelf ? 'You cannot delete your own account' : `Permanently delete ${account.email}`} aria-label={`Delete account ${account.email}`}><Trash2 size={13}/><span>Delete</span></button></div></td></tr> })}
          {!visibleAccounts.length && <tr><td colSpan={9} className="empty-row">No matching accounts.</td></tr>}
        </tbody></table></div>
      </div>}
      {tab === 'alerts' && <div className="admin-section">
        <div className="admin-section-heading"><div><h2>Central alerts</h2><p>Current stock, expiry, purchasing, and workspace status signals across all businesses.</p></div><span className={alerts.length ? 'alert-count has-alerts' : 'alert-count'}>{alerts.length ? `${alerts.length} active alerts` : 'All clear'}</span></div>
        <div className="admin-alert-list">{alerts.map(alert => <article className={`admin-alert ${alert.severity}`} key={alert.id}><span className="alert-severity"/><div><strong>{alert.kind}</strong><small>{alert.business_name} · {alert.count} {alert.count === 1 ? 'item' : 'items'}</small></div><span className="alert-pill">{alert.severity}</span></article>)}{!alerts.length && <div className="empty-state">No business alerts right now.</div>}</div>
      </div>}
      {tab === 'activity' && <div className="admin-section">
        <div className="admin-section-heading"><div><h2>Audit log</h2><p>Recent account actions and data changes recorded by the application.</p></div><button className="secondary-button" onClick={exportActivity} disabled={!events.length}><Download size={15}/>Export CSV</button></div>
        <div className="table-wrap"><table className="admin-table activity-table"><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Resource</th><th>Reference</th><th>Details</th></tr></thead><tbody>
          {events.map(event => <tr key={event.id}><td>{readableDate(event.created_at)}</td><td><strong>{event.actor}</strong><small>{event.actor_email || 'System generated'}</small></td><td><span className="audit-action">{event.action.replaceAll('_', ' ')}</span></td><td>{event.entity.replaceAll('_', ' ')}</td><td>#{event.entity_id}</td><td className="audit-details" title={JSON.stringify(event.details)}>{Object.keys(event.details).length ? JSON.stringify(event.details) : '—'}</td></tr>)}
          {!events.length && <tr><td colSpan={6} className="empty-row">No audit events have been recorded.</td></tr>}
        </tbody></table></div>
        <p className="admin-footnote"><Activity size={15}/><span>Showing the latest {events.length} events (up to 100). Export downloads this visible set.</span></p>
      </div>}
    </section>
  </div>
}
