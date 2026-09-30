import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Edit2,
  FileCheck2,
  FilePlus,
  History,
  Layers,
  Package,
  Plus,
  RefreshCw,
  ShoppingCart,
  Trash2,
  TrendingUp,
  Truck
} from 'lucide-react'
import { api } from '../lib/api'
import type { ReorderItem, ReorderOverview, User } from '../types'

export default function ReorderPage({ currentUser }: { currentUser: User }) {
  const [data, setData] = useState<ReorderOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'low_stock' | 'previously_ordered' | 'suggested' | 'frequently_ordered' | 'pending' | 'completed'>('low_stock')
  const [busyItem, setBusyItem] = useState<number | null>(null)
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)

  // Quantity editing state
  const [editingItemId, setEditingItemId] = useState<number | null>(null)
  const [editQty, setEditQty] = useState<number>(10)

  async function loadOverview() {
    setLoading(true)
    setError(null)
    try {
      const res = await api<ReorderOverview>('/api/reorders/overview')
      setData(res)
      if (res.pending_reorders.length > 0 && !selectedSupplierId) {
        setSelectedSupplierId(res.pending_reorders[0].supplier_id || 1)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reorder overview')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOverview()
  }, [])

  async function addToReorder(item: ReorderItem, qty?: number) {
    setBusyItem(item.product_id)
    try {
      const selectedQty = qty || item.suggested_quantity || 10
      await api('/api/reorders/item', {
        method: 'POST',
        body: JSON.stringify({
          product_id: item.product_id,
          supplier_id: item.supplier_id,
          suggested_quantity: item.suggested_quantity,
          selected_quantity: selectedQty,
          source: 'reorder_hub'
        })
      })
      setSuccessNotice(`Added "${item.product_name}" (Qty: ${selectedQty}) to pending reorder list.`)
      setTimeout(() => setSuccessNotice(null), 4000)
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Could not add item to reorder list')
    } finally {
      setBusyItem(null)
    }
  }

  async function updatePendingItemQty(id: number) {
    try {
      await api(`/api/reorders/item/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ selected_quantity: editQty })
      })
      setEditingItemId(null)
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Could not update quantity')
    }
  }

  async function removePendingItem(id: number) {
    try {
      await api(`/api/reorders/item/${id}`, { method: 'DELETE' })
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Could not remove item')
    }
  }

  async function createPurchaseOrder() {
    if (!data || data.pending_reorders.length === 0) return
    const ids = data.pending_reorders.map(i => i.id)
    const supId = selectedSupplierId || (data.pending_reorders[0]?.supplier_id ?? 1)

    try {
      const res = await api<{ message: string; po_number: string }>('/api/reorders/create-po', {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: supId,
          reorder_item_ids: ids,
        })
      })
      setSuccessNotice(`Official Purchase Order created: ${res.po_number}!`)
      setTimeout(() => setSuccessNotice(null), 6000)
      setActiveTab('completed')
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create purchase order')
    }
  }

  async function reorderFromPrevious(purchaseId: number) {
    try {
      const res = await api<{ po_number: string; message: string }>(`/api/reorders/reorder-previous/${purchaseId}`, {
        method: 'POST'
      })
      setSuccessNotice(`Generated draft PO ${res.po_number} from previous purchase history!`)
      setTimeout(() => setSuccessNotice(null), 6000)
      setActiveTab('completed')
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to reorder from purchase history')
    }
  }

  if (loading && !data) {
    return <div className="p-8 text-center text-slate-400">Loading live business reorder metrics…</div>
  }

  const pendingTotal = data?.pending_reorders.reduce((sum, item) => sum + (item.estimated_cost || 0), 0) || 0

  return (
    <div className="reorder-page space-y-6 p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-700/60 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <ShoppingCart size={22} />
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white">Reorder Management Hub</h1>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Purchase history-driven reordering, low-stock replenishment, and instant Purchase Order generation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab('pending')}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition shadow-lg shadow-indigo-600/20"
          >
            <ShoppingCart size={16} />
            <span>Pending Reorders ({data?.pending_reorders.length || 0})</span>
          </button>
          <button
            onClick={loadOverview}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Refresh reorder data"
          >
            <RefreshCw size={17} />
          </button>
        </div>
      </div>

      {successNotice && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={18} className="text-emerald-400" />
            <span>{successNotice}</span>
          </div>
          <button onClick={() => setSuccessNotice(null)} className="text-xs text-emerald-400 hover:underline">Dismiss</button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-2">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Stats Overview */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-850/80 border border-slate-700/60 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
            <AlertTriangle size={14} /> Low Stock Items
          </div>
          <div className="text-2xl font-bold text-white mt-1.5">{data?.low_stock.length || 0}</div>
          <div className="text-xs text-slate-400 mt-1">Requires immediate replenishment</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-850/80 border border-slate-700/60 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
            <History size={14} /> Order History Items
          </div>
          <div className="text-2xl font-bold text-white mt-1.5">{data?.previously_ordered.length || 0}</div>
          <div className="text-xs text-slate-400 mt-1">From actual verified purchases</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-850/80 border border-slate-700/60 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
            <ShoppingCart size={14} /> In Reorder Basket
          </div>
          <div className="text-2xl font-bold text-white mt-1.5">{data?.pending_reorders.length || 0}</div>
          <div className="text-xs text-slate-400 mt-1">Estimated: ₹{pendingTotal.toLocaleString()}</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-850/80 border border-slate-700/60 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
            <FileCheck2 size={14} /> Generated POs
          </div>
          <div className="text-2xl font-bold text-white mt-1.5">{data?.completed_reorders.length || 0}</div>
          <div className="text-xs text-slate-400 mt-1">Purchase orders issued</div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-700/70 overflow-x-auto space-x-2 scrollbar-none">
        <button
          onClick={() => setActiveTab('low_stock')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'low_stock'
              ? 'border-rose-500 text-rose-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertTriangle size={15} />
          <span>Low Stock ({data?.low_stock.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('previously_ordered')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'previously_ordered'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <History size={15} />
          <span>Previously Ordered</span>
        </button>

        <button
          onClick={() => setActiveTab('suggested')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'suggested'
              ? 'border-amber-500 text-amber-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <TrendingUp size={15} />
          <span>Suggested Reorders</span>
        </button>

        <button
          onClick={() => setActiveTab('frequently_ordered')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'frequently_ordered'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers size={15} />
          <span>Frequently Ordered</span>
        </button>

        <button
          onClick={() => setActiveTab('pending')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'pending'
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShoppingCart size={15} />
          <span>Reorder Basket ({data?.pending_reorders.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('completed')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'completed'
              ? 'border-purple-500 text-purple-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileCheck2 size={15} />
          <span>Completed Orders ({data?.completed_reorders.length || 0})</span>
        </button>
      </div>

      {/* Tab Content 1: Low Stock Replenishment */}
      {activeTab === 'low_stock' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Products Below Reorder Threshold</h2>
            <span className="text-xs text-slate-400">Triggered when Current Stock ≤ Reorder Level</span>
          </div>

          {(!data?.low_stock || data.low_stock.length === 0) ? (
            <div className="p-12 text-center rounded-xl bg-slate-850 border border-slate-700/60 text-slate-400">
              <CheckCircle2 size={36} className="mx-auto text-emerald-400 mb-2 opacity-80" />
              <p className="font-medium text-white">All product stock levels are healthy.</p>
              <p className="text-sm mt-1">No products are currently at or below their reorder threshold.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">Product</th>
                    <th className="py-3 px-4">Current Stock</th>
                    <th className="py-3 px-4">Reorder Level</th>
                    <th className="py-3 px-4">Last Order</th>
                    <th className="py-3 px-4">Supplier</th>
                    <th className="py-3 px-4">Suggested Reorder</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {data.low_stock.map((item) => (
                    <tr key={item.product_id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4">
                        <div className="font-medium text-white">{item.product_name}</div>
                        <div className="text-xs text-slate-500 font-mono">{item.sku}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          {item.current_stock}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-300">{item.reorder_level}</td>
                      <td className="py-3 px-4 text-xs">
                        {item.last_order_quantity ? (
                          <div>
                            <span className="font-semibold text-white">{item.last_order_quantity} units</span>
                            <div className="text-slate-500">{item.last_order_date || 'Past order'}</div>
                          </div>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-300">{item.supplier_name}</td>
                      <td className="py-3 px-4 font-semibold text-emerald-400">
                        {item.suggested_quantity} units
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => addToReorder(item)}
                          disabled={busyItem === item.product_id}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition shadow-sm"
                        >
                          <Plus size={14} />
                          <span>Add to Reorder</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab Content 2: Previously Ordered Items */}
      {activeTab === 'previously_ordered' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Purchase History Reordering</h2>
            <span className="text-xs text-slate-400">Products with verified previous orders</span>
          </div>

          {(!data?.previously_ordered || data.previously_ordered.length === 0) ? (
            <div className="p-12 text-center rounded-xl bg-slate-850 border border-slate-700/60 text-slate-400">
              <History size={36} className="mx-auto text-slate-500 mb-2 opacity-60" />
              <p className="font-medium text-white">No historical purchase orders yet.</p>
              <p className="text-sm mt-1">Items will populate here automatically as receipts and invoices are confirmed.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">Product</th>
                    <th className="py-3 px-4">Current Stock</th>
                    <th className="py-3 px-4">Supplier</th>
                    <th className="py-3 px-4">Last Price</th>
                    <th className="py-3 px-4">Last Qty</th>
                    <th className="py-3 px-4">Last Date</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {data.previously_ordered.map((item, idx) => (
                    <tr key={`${item.product_id}-${idx}`} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4">
                        <div className="font-medium text-white">{item.product_name}</div>
                        <div className="text-xs text-slate-500 font-mono">{item.sku}</div>
                      </td>
                      <td className="py-3 px-4 font-mono">{item.current_stock}</td>
                      <td className="py-3 px-4 text-xs text-slate-300">{item.supplier_name}</td>
                      <td className="py-3 px-4 font-mono text-xs">₹{item.previous_price}</td>
                      <td className="py-3 px-4 font-semibold text-white">{item.last_order_quantity}</td>
                      <td className="py-3 px-4 text-xs text-slate-400">{item.last_order_date || 'Recent'}</td>
                      <td className="py-3 px-4 text-right space-x-2">
                        <button
                          onClick={() => addToReorder(item, item.last_order_quantity)}
                          disabled={busyItem === item.product_id}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition"
                        >
                          <Plus size={13} />
                          <span>Reorder ({item.last_order_quantity})</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab Content 3: Suggested Reorders */}
      {activeTab === 'suggested' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Algorithm & Stock Velocity Suggestions</h2>
            <span className="text-xs text-slate-400">Human approval is required before purchase</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data?.suggested_reorders.map((item) => (
              <div key={item.product_id} className="p-4 rounded-xl bg-slate-850 border border-slate-700/60 flex flex-col justify-between">
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold text-white text-base">{item.product_name}</h3>
                      <p className="text-xs text-slate-400 mt-0.5">Supplier: {item.supplier_name}</p>
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      {item.reason}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 mt-4 p-3 rounded-lg bg-slate-800/60 text-xs">
                    <div>
                      <div className="text-slate-400">Current Stock</div>
                      <div className="text-sm font-bold text-white mt-0.5">{item.current_stock}</div>
                    </div>
                    <div>
                      <div className="text-slate-400">Reorder Level</div>
                      <div className="text-sm font-bold text-white mt-0.5">{item.reorder_level}</div>
                    </div>
                    <div>
                      <div className="text-slate-400">Suggested</div>
                      <div className="text-sm font-bold text-emerald-400 mt-0.5">{item.suggested_quantity} units</div>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-700/50 flex items-center justify-between">
                  <span className="text-xs text-slate-400">Last order: {item.last_order_quantity || 15} units</span>
                  <button
                    onClick={() => addToReorder(item, item.suggested_quantity)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition"
                  >
                    <Plus size={14} />
                    <span>Accept & Add to PO</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab Content 4: Frequently Ordered */}
      {activeTab === 'frequently_ordered' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Frequently Ordered Products</h2>
            <span className="text-xs text-slate-400">Ranked by total historical purchase order volume</span>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                <tr>
                  <th className="py-3 px-4">Product</th>
                  <th className="py-3 px-4">Times Ordered</th>
                  <th className="py-3 px-4">Avg Order Qty</th>
                  <th className="py-3 px-4">Current Stock</th>
                  <th className="py-3 px-4">Supplier</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60">
                {data?.frequently_ordered.map((item) => (
                  <tr key={item.product_id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4">
                      <div className="font-medium text-white">{item.product_name}</div>
                      <div className="text-xs text-slate-500 font-mono">{item.sku}</div>
                    </td>
                    <td className="py-3 px-4 font-semibold text-indigo-400">
                      <span className="px-2.5 py-0.5 rounded-full text-xs bg-indigo-500/10 border border-indigo-500/20">
                        {item.order_count || 1} times
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono">{item.average_quantity || 20}</td>
                    <td className="py-3 px-4 font-mono">{item.current_stock}</td>
                    <td className="py-3 px-4 text-xs text-slate-300">{item.supplier_name}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => addToReorder(item, item.average_quantity || 20)}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition"
                      >
                        <Plus size={13} />
                        <span>Add Reorder ({item.average_quantity || 20})</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab Content 5: Pending Reorder Basket */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <ShoppingCart size={20} className="text-indigo-400" />
                <span>Pending Reorder Items ({data?.pending_reorders.length || 0})</span>
              </h2>
              <p className="text-xs text-indigo-200/70 mt-0.5">
                Review and adjust quantities. Click "Generate Purchase Order" to formalize the order.
              </p>
            </div>

            {data?.pending_reorders && data.pending_reorders.length > 0 && (
              <button
                onClick={createPurchaseOrder}
                className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition shadow-lg shadow-emerald-600/20 flex items-center gap-2"
              >
                <FileCheck2 size={17} />
                <span>Generate Official Purchase Order</span>
              </button>
            )}
          </div>

          {(!data?.pending_reorders || data.pending_reorders.length === 0) ? (
            <div className="p-12 text-center rounded-xl bg-slate-850 border border-slate-700/60 text-slate-400">
              <ShoppingCart size={36} className="mx-auto text-slate-500 mb-2 opacity-60" />
              <p className="font-medium text-white">Reorder basket is currently empty.</p>
              <p className="text-sm mt-1">Browse Low Stock or Previously Ordered tabs and click "Add to Reorder".</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">Product</th>
                    <th className="py-3 px-4">Supplier</th>
                    <th className="py-3 px-4">Current Stock</th>
                    <th className="py-3 px-4">Order Quantity (Editable)</th>
                    <th className="py-3 px-4">Est. Cost</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {data.pending_reorders.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4">
                        <div className="font-medium text-white">{item.product_name}</div>
                        <div className="text-xs text-slate-500 font-mono">{item.sku}</div>
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-300">{item.supplier_name}</td>
                      <td className="py-3 px-4 font-mono">{item.current_stock}</td>
                      <td className="py-3 px-4">
                        {editingItemId === item.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="number"
                              min="1"
                              value={editQty}
                              onChange={(e) => setEditQty(Number(e.target.value))}
                              className="w-20 px-2 py-1 rounded bg-slate-900 border border-indigo-500 text-white text-sm"
                            />
                            <button
                              onClick={() => updatePendingItemQty(item.id)}
                              className="px-2 py-1 rounded bg-indigo-600 text-white text-xs font-semibold"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => setEditingItemId(null)}
                              className="text-xs text-slate-400 hover:text-white"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white text-base">{item.selected_quantity}</span>
                            <button
                              onClick={() => {
                                setEditingItemId(item.id)
                                setEditQty(item.selected_quantity)
                              }}
                              className="p-1 text-slate-400 hover:text-indigo-400"
                              title="Edit quantity"
                            >
                              <Edit2 size={13} />
                            </button>
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono font-semibold text-emerald-400">
                        ₹{(item.estimated_cost || 0).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => removePendingItem(item.id)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition"
                          title="Remove item"
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="p-4 bg-slate-900/60 border-t border-slate-700/60 flex items-center justify-between">
                <span className="text-sm text-slate-400">Total Items: {data.pending_reorders.length}</span>
                <div className="text-right">
                  <span className="text-xs text-slate-400">Estimated Total Amount: </span>
                  <span className="text-lg font-bold text-emerald-400">₹{pendingTotal.toLocaleString()}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab Content 6: Completed Purchase Orders */}
      {activeTab === 'completed' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Purchase Orders History</h2>
            <span className="text-xs text-slate-400">Generated from reorder workflow</span>
          </div>

          {(!data?.completed_reorders || data.completed_reorders.length === 0) ? (
            <div className="p-12 text-center rounded-xl bg-slate-850 border border-slate-700/60 text-slate-400">
              <FileCheck2 size={36} className="mx-auto text-slate-500 mb-2 opacity-60" />
              <p className="font-medium text-white">No purchase orders created yet.</p>
              <p className="text-sm mt-1">Select items in the reorder basket and generate your first PO.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">PO Number</th>
                    <th className="py-3 px-4">Supplier</th>
                    <th className="py-3 px-4">Items Count</th>
                    <th className="py-3 px-4">Total Amount</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Created Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {data.completed_reorders.map((po) => (
                    <tr key={po.id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4 font-mono font-medium text-white">{po.po_number}</td>
                      <td className="py-3 px-4 text-xs text-slate-300">{po.supplier_name}</td>
                      <td className="py-3 px-4 font-mono">{po.item_count} items</td>
                      <td className="py-3 px-4 font-semibold text-emerald-400 font-mono">
                        ₹{(po.total_amount || 0).toLocaleString()}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          po.status === 'received'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : po.status === 'approved'
                            ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                            : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        }`}>
                          {po.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-400">
                        {po.created_at ? new Date(po.created_at).toLocaleDateString() : 'Recent'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
