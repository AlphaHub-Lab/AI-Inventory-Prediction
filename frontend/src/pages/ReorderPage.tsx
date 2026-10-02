import { useEffect, useState, useRef } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Barcode,
  Calendar,
  CheckCircle2,
  CheckSquare,
  ChevronDown,
  Clock,
  DollarSign,
  Download,
  Edit2,
  FileCheck2,
  FileSpreadsheet,
  Filter,
  History,
  Info,
  Layers,
  Package,
  Plus,
  RefreshCw,
  Search,
  ShoppingCart,
  Square,
  Tag,
  Trash2,
  TrendingUp,
  Truck,
  UploadCloud,
  X
} from 'lucide-react'
import { api } from '../lib/api'
import type {
  PendingReorderItem,
  ReceivingHistoryItem,
  ReorderItem,
  ReorderOverview,
  StoreCapability,
  User,
  WholesalerCandidate,
  WholesalerDocResponse,
  WholesalerItem
} from '../types'

interface CatalogSearchItem {
  product_id: number
  sku: string
  barcode?: string | null
  product_name: string
  category?: string | null
  current_stock: number
  reorder_level: number
  target_stock?: number
  purchase_price: number
  supplier_id?: number | null
  supplier_name: string
  unit?: string
  pack_size?: string | null
  size?: string | null
  color?: string | null
  style?: string | null
  variant_name?: string | null
}

interface ReceiveModalItem {
  reorder_id?: number
  product_id: number
  product_name: string
  sku: string
  barcode?: string | null
  current_stock: number
  requested_quantity: number
  already_received: number
  received_quantity: number
  unit: string
  batch_number: string
  serial_number: string
  expiry_date: string
  purchase_price: number
  size?: string | null
  color?: string | null
  style?: string | null
}

interface DuplicatePromptData {
  product_id: number
  product_name: string
  existing_reorder_id: number
  current_requested_quantity: number
  already_received_quantity: number
  status: string
  new_quantity: number
  reason: string
}

export default function ReorderPage({ currentUser }: { currentUser: User }) {
  const [data, setData] = useState<ReorderOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<
    'pending' | 'low_stock' | 'expired_stock' | 'expiring_soon' | 'previously_ordered' | 'suggested' | 'frequently_ordered' | 'completed' | 'history'
  >('pending')
  const [busyItem, setBusyItem] = useState<number | null>(null)
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)

  // Quantity editing state
  const [editingItemId, setEditingItemId] = useState<number | null>(null)
  const [editQty, setEditQty] = useState<number>(10)

  // Multi-selection for pending reorders
  const [selectedItemIds, setSelectedItemIds] = useState<number[]>([])

  // Modal 1: Manual Add to Reorder
  const [showAddModal, setShowAddModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<CatalogSearchItem[]>([])
  const [searchingCatalog, setSearchingCatalog] = useState(false)
  const [selectedCatalogProduct, setSelectedCatalogProduct] = useState<CatalogSearchItem | null>(null)
  const [manualAddQty, setManualAddQty] = useState<number>(10)
  const [manualAddReason, setManualAddReason] = useState<string>('Manual replenishment order')
  const [duplicatePrompt, setDuplicatePrompt] = useState<DuplicatePromptData | null>(null)

  // Modal 2: Stock Receiving Modal (Physical Stock Arrival)
  const [showReceiveModal, setShowReceiveModal] = useState(false)
  const [receiveItemsList, setReceiveItemsList] = useState<ReceiveModalItem[]>([])
  const [generalReceiveNote, setGeneralReceiveNote] = useState('Stock arrived at warehouse/store')
  const [receivingSubmitting, setReceivingSubmitting] = useState(false)

  // Modal 3: Wholesaler Document Upload (Any format: CSV, Excel, PDF, Image, etc.)
  const [showWholesalerModal, setShowWholesalerModal] = useState(false)
  const [wholesalerFile, setWholesalerFile] = useState<File | null>(null)
  const [wholesalerUploading, setWholesalerUploading] = useState(false)
  const [wholesalerData, setWholesalerData] = useState<WholesalerDocResponse | null>(null)
  const [wholesalerConfirming, setWholesalerConfirming] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // History Tab sub-toggle ('reorders' | 'receipts')
  const [historySubTab, setHistorySubTab] = useState<'reorders' | 'receipts'>('reorders')
  const [historySearch, setHistorySearch] = useState('')

  // Store capability helpers
  const capability: StoreCapability = data?.store_capability || {
    name: 'Universal Store',
    business_type: currentUser.business_type || 'grocery',
    units: ['unit', 'kg', 'g', 'L', 'ml', 'piece', 'pack', 'box', 'set', 'pair'],
    default_unit: 'unit',
    allow_decimals: true,
    expiry_warning_days: 7,
    features: {
      weight: true,
      expiry: currentUser.business_type !== 'clothing' && currentUser.business_type !== 'stationery',
      batch: true,
      serial_number: true,
      size: currentUser.business_type === 'clothing',
      color: currentUser.business_type === 'clothing',
      variants: currentUser.business_type === 'clothing',
      pack_size: true
    }
  }

  const isClothing = capability.features.variants || capability.business_type === 'clothing'
  const supportsExpiry = capability.features.expiry ?? false
  const supportsBatch = capability.features.batch ?? true
  const supportsSerial = capability.features.serial_number ?? false
  const supportsPackSize = capability.features.pack_size ?? false
  const allowDecimals = capability.allow_decimals ?? true

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

  // Auto-sync Low & Expired stock
  async function triggerAutoSync() {
    try {
      const res = await api<{ message: string; synced_count: number }>('/api/reorders/auto-populate', {
        method: 'POST'
      })
      setSuccessNotice(res.message)
      setTimeout(() => setSuccessNotice(null), 5000)
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Sync failed')
    }
  }

  // 1. Export CSV
  async function handleExportCSV() {
    try {
      const token = sessionStorage.getItem('inventory_access_token') || ''
      let exportUrl = '/api/reorders/export-csv'
      if (selectedItemIds.length > 0) {
        exportUrl += `?ids=${selectedItemIds.join(',')}`
      }
      const response = await fetch(exportUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      })
      if (!response.ok) throw new Error('Failed to generate CSV sheet')
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `reorder-stock-${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      setSuccessNotice('CSV sheet exported successfully with preserved barcodes and formatted columns!')
      setTimeout(() => setSuccessNotice(null), 4000)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to export CSV')
    }
  }

  // Add Item to Reorder List
  async function addToReorder(item: ReorderItem, qty?: number, reason?: string) {
    setBusyItem(item.product_id)
    try {
      const selectedQty = qty || item.suggested_quantity || (allowDecimals ? 10.0 : 10)
      await api('/api/reorders/item', {
        method: 'POST',
        body: JSON.stringify({
          product_id: item.product_id,
          supplier_id: item.supplier_id,
          suggested_quantity: item.suggested_quantity,
          selected_quantity: selectedQty,
          source: item.source || 'reorder_hub',
          reason: reason || item.reason || 'Replenishment order',
          mode: 'increase'
        })
      })
      setSuccessNotice(`Added "${item.product_name}" (Qty: ${selectedQty} ${item.unit || ''}) to reorder basket.`)
      setTimeout(() => setSuccessNotice(null), 4000)
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Could not add item to reorder list')
    } finally {
      setBusyItem(null)
    }
  }

  // Search Catalog for Manual Add
  async function searchCatalog(query: string) {
    setSearchQuery(query)
    if (query.trim().length < 1) {
      setSearchResults([])
      return
    }
    setSearchingCatalog(true)
    try {
      const results = await api<CatalogSearchItem[]>(`/api/reorders/catalog-search?q=${encodeURIComponent(query.trim())}`)
      setSearchResults(results)
    } catch {
      setSearchResults([])
    } finally {
      setSearchingCatalog(false)
    }
  }

  async function handleManualAddSubmit(mode: 'prompt' | 'increase' | 'replace' = 'prompt') {
    if (!selectedCatalogProduct && !duplicatePrompt) return
    const prodId = selectedCatalogProduct?.product_id || duplicatePrompt?.product_id
    const prodName = selectedCatalogProduct?.product_name || duplicatePrompt?.product_name
    const qty = duplicatePrompt ? duplicatePrompt.new_quantity : manualAddQty
    const reason = duplicatePrompt ? duplicatePrompt.reason : manualAddReason

    try {
      const res = await api<{
        duplicate?: boolean
        existing_reorder_id?: number
        current_requested_quantity?: number
        already_received_quantity?: number
        status?: string
        message?: string
        reorder_id?: number
      }>('/api/reorders/item', {
        method: 'POST',
        body: JSON.stringify({
          product_id: prodId,
          supplier_id: selectedCatalogProduct?.supplier_id,
          suggested_quantity: qty,
          selected_quantity: qty,
          source: 'manual',
          reason: reason || 'Manual store addition',
          mode: mode
        })
      })

      if (res.duplicate && res.existing_reorder_id) {
        setDuplicatePrompt({
          product_id: prodId!,
          product_name: prodName!,
          existing_reorder_id: res.existing_reorder_id,
          current_requested_quantity: res.current_requested_quantity || 0,
          already_received_quantity: res.already_received_quantity || 0,
          status: res.status || 'pending',
          new_quantity: qty,
          reason: reason
        })
        return
      }

      setSuccessNotice(res.message || `Added "${prodName}" to reorder basket!`)
      setTimeout(() => setSuccessNotice(null), 4000)
      setShowAddModal(false)
      setSelectedCatalogProduct(null)
      setDuplicatePrompt(null)
      setSearchQuery('')
      setSearchResults([])
      await loadOverview()
      setActiveTab('pending')
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to add product')
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

  async function removePendingItem(id: number, productName: string) {
    if (!window.confirm(`Are you sure you want to remove "${productName}" from the pending reorder list? (This will not delete the product itself).`)) {
      return
    }
    try {
      await api(`/api/reorders/item/${id}`, { method: 'DELETE' })
      setSelectedItemIds(prev => prev.filter(x => x !== id))
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Could not remove item')
    }
  }

  // Multi-Selection Logic
  const allPendingIds = data?.pending_reorders.map(i => i.id) || []
  const isAllSelected = allPendingIds.length > 0 && allPendingIds.every(id => selectedItemIds.includes(id))

  function toggleSelectAll() {
    if (isAllSelected) {
      setSelectedItemIds([])
    } else {
      setSelectedItemIds(allPendingIds)
    }
  }

  function toggleSelectItem(id: number) {
    setSelectedItemIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  // 2. Physical Stock Receiving Flow
  function openReceiveModalForItems(itemsToReceive: PendingReorderItem[]) {
    if (!itemsToReceive || itemsToReceive.length === 0) return
    const modalItems: ReceiveModalItem[] = itemsToReceive.map(item => {
      const remaining = Math.max((item.selected_quantity || 0) - (item.received_quantity || 0), 0)
      return {
        reorder_id: item.id,
        product_id: item.product_id,
        product_name: item.product_name,
        sku: item.sku,
        barcode: item.barcode || null,
        current_stock: item.current_stock,
        requested_quantity: item.selected_quantity || 10,
        already_received: item.received_quantity || 0,
        received_quantity: remaining > 0 ? remaining : item.selected_quantity || 10,
        unit: item.unit || 'unit',
        batch_number: `LOT-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${item.product_id}`,
        serial_number: '',
        expiry_date: '',
        purchase_price: item.purchase_price || 0,
        size: item.size,
        color: item.color,
        style: item.style
      }
    })
    setReceiveItemsList(modalItems)
    setShowReceiveModal(true)
  }

  function openReceiveModalForSingle(item: PendingReorderItem) {
    openReceiveModalForItems([item])
  }

  function openReceiveModalForSelected() {
    if (!data) return
    const selected = data.pending_reorders.filter(item => selectedItemIds.includes(item.id))
    if (selected.length === 0) {
      alert('Please select at least one item from the table to receive into stock.')
      return
    }
    openReceiveModalForItems(selected)
  }

  async function handleConfirmReceiveStock() {
    if (receiveItemsList.length === 0) return
    setReceivingSubmitting(true)
    try {
      const payload = {
        items: receiveItemsList.map(item => ({
          reorder_id: item.reorder_id,
          product_id: item.product_id,
          received_quantity: item.received_quantity,
          batch_number: item.batch_number || null,
          serial_number: item.serial_number || null,
          expiry_date: item.expiry_date || null,
          purchase_price: item.purchase_price,
          barcode: item.barcode || null,
          size: item.size || null,
          color: item.color || null,
          note: `Received into local stock | Qty: ${item.received_quantity} ${item.unit} (Batch: ${item.batch_number || 'N/A'}, S/N: ${item.serial_number || 'N/A'})`
        })),
        general_note: generalReceiveNote
      }

      const res = await api<{ message: string; received_count: number; total_units: number }>('/api/reorders/receive', {
        method: 'POST',
        body: JSON.stringify(payload)
      })

      setSuccessNotice(res.message)
      setTimeout(() => setSuccessNotice(null), 6000)
      setShowReceiveModal(false)
      setSelectedItemIds([])
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Stock receiving failed')
    } finally {
      setReceivingSubmitting(false)
    }
  }

  // 3. Wholesaler Multi-format Document Ingestion
  async function handleWholesalerFileUpload(file: File) {
    setWholesalerFile(file)
    setWholesalerUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await api<WholesalerDocResponse>('/api/reorders/upload-wholesaler', {
        method: 'POST',
        body: formData
      })
      setWholesalerData(res)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to parse wholesaler document')
      setWholesalerFile(null)
    } finally {
      setWholesalerUploading(false)
    }
  }

  // Change matched candidate for an ambiguous row
  function handleSelectCandidate(rowIndex: number, candidate: WholesalerCandidate) {
    if (!wholesalerData) return
    setWholesalerData(prev => {
      if (!prev) return null
      const updatedItems = [...prev.items]
      updatedItems[rowIndex] = {
        ...updatedItems[rowIndex],
        matched_product_id: candidate.product_id,
        matched_product_name: candidate.product_name,
        barcode: candidate.barcode || updatedItems[rowIndex].barcode,
        size: candidate.size || updatedItems[rowIndex].size,
        color: candidate.color || updatedItems[rowIndex].color,
        status: 'matched',
        error_message: null
      }
      return {
        ...prev,
        items: updatedItems,
        summary: prev.summary
          ? {
              ...prev.summary,
              matched: updatedItems.filter(i => i.status === 'matched').length,
              needs_review: updatedItems.filter(i => i.status === 'needs_review').length,
              ready_to_add: updatedItems.filter(i => i.status === 'matched').length
            }
          : undefined
      }
    })
  }

  async function handleConfirmWholesalerIntoStock() {
    if (!wholesalerData || wholesalerData.items.length === 0) return
    const readyItems = wholesalerData.items.filter(i => i.status === 'matched' && i.quantity > 0)
    if (readyItems.length === 0) {
      alert('No matched items are ready to import. Please review ambiguous items first.')
      return
    }

    setWholesalerConfirming(true)
    try {
      const payload = {
        supplier_name: wholesalerData.supplier_name || 'Wholesaler',
        invoice_number: wholesalerData.invoice_number,
        file_hash: wholesalerData.file_hash,
        items: readyItems.map(i => ({
          product_id: i.matched_product_id,
          product_name: i.matched_product_name || i.raw_product_name,
          quantity: i.quantity,
          unit: i.unit || 'unit',
          barcode: i.barcode,
          serial_number: i.serial_number,
          batch_number: i.batch_number,
          expiry_date: i.expiry_date,
          purchase_price: i.purchase_price || 0.0,
          mrp: i.mrp,
          size: i.size,
          color: i.color,
          style: i.style,
          variant_name: i.variant_name
        }))
      }

      const res = await api<{ message: string; imported_count: number; total_units: number }>('/api/reorders/confirm-wholesaler', {
        method: 'POST',
        body: JSON.stringify(payload)
      })

      setSuccessNotice(res.message)
      setTimeout(() => setSuccessNotice(null), 6000)
      setShowWholesalerModal(false)
      setWholesalerData(null)
      setWholesalerFile(null)
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to confirm wholesaler items into stock')
    } finally {
      setWholesalerConfirming(false)
    }
  }

  // Generate Purchase Order from selected or all
  async function createPurchaseOrder() {
    if (!data || data.pending_reorders.length === 0) return
    const ids = selectedItemIds.length > 0 ? selectedItemIds : data.pending_reorders.map(i => i.id)
    const supId = selectedSupplierId || (data.pending_reorders[0]?.supplier_id ?? 1)

    try {
      const res = await api<{ message: string; po_number: string }>('/api/reorders/create-po', {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: supId,
          reorder_item_ids: ids
        })
      })
      setSuccessNotice(`Official Purchase Order created: ${res.po_number}!`)
      setTimeout(() => setSuccessNotice(null), 6000)
      setSelectedItemIds([])
      setActiveTab('completed')
      await loadOverview()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create purchase order')
    }
  }

  if (loading && !data) {
    return <div className="p-8 text-center text-slate-400">Loading live business reorder metrics…</div>
  }

  const pendingTotal = data?.pending_reorders.reduce((sum, item) => sum + (item.estimated_cost || 0), 0) || 0
  const summary = data?.summary || {
    total_reorders: data?.pending_reorders.length || 0,
    low_stock_count: data?.low_stock.length || 0,
    expired_count: data?.expired_stock.length || 0,
    expiring_soon_count: data?.expiring_soon_stock?.length || 0,
    manual_reorders_count: data?.pending_reorders.filter(i => i.source === 'manual').length || 0,
    partially_received_count: data?.pending_reorders.filter(i => i.status === 'partially_received').length || 0
  }

  // Filter history
  const filteredReorderHistory = (data?.pending_reorders || []).filter(item => {
    if (!historySearch.trim()) return true
    const term = historySearch.toLowerCase()
    return (
      item.product_name.toLowerCase().includes(term) ||
      item.sku.toLowerCase().includes(term) ||
      (item.barcode && item.barcode.toLowerCase().includes(term))
    )
  })

  const filteredReceiptHistory = (data?.receiving_history || []).filter(item => {
    if (!historySearch.trim()) return true
    const term = historySearch.toLowerCase()
    return (
      item.product_name.toLowerCase().includes(term) ||
      item.sku.toLowerCase().includes(term) ||
      (item.barcode && item.barcode.toLowerCase().includes(term)) ||
      (item.lot_number && item.lot_number.toLowerCase().includes(term)) ||
      (item.serial_number && item.serial_number.toLowerCase().includes(term))
    )
  })

  return (
    <div className="reorder-page space-y-6 p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-700/60 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <span className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-sm">
              <ShoppingCart size={24} />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-white">Universal Reorder & Stock Engine</h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 capitalize">
                  {capability.name}
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-0.5">
                Low stock & expiry detection, decimal weight/count handling, CSV export, physical stock receiving, and supplier file import.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Export CSV Button */}
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-emerald-600/90 hover:bg-emerald-500 text-white font-medium text-xs md:text-sm transition shadow-sm"
            title="Download formatted UTF-8 reorder sheet in .CSV with string-preserved barcodes and store-specific columns"
          >
            <Download size={16} />
            <span>Export CSV</span>
          </button>

          {/* Upload Wholesaler Order */}
          <button
            onClick={() => setShowWholesalerModal(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs md:text-sm transition shadow-sm"
            title="Upload wholesaler invoice in CSV, Excel, PDF, or Image format to extract and match products"
          >
            <UploadCloud size={16} />
            <span>Import Delivery File</span>
          </button>

          {/* Add Product Manually */}
          <button
            onClick={() => {
              setShowAddModal(true)
              setSelectedCatalogProduct(null)
              setDuplicatePrompt(null)
            }}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium text-xs md:text-sm transition shadow-sm"
          >
            <Plus size={16} />
            <span>Add Item</span>
          </button>

          {/* Pending Basket Shortcut */}
          <button
            onClick={() => setActiveTab('pending')}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs md:text-sm transition shadow-lg shadow-indigo-600/20"
          >
            <ShoppingCart size={16} />
            <span>Reorder List ({summary.total_reorders})</span>
          </button>

          {/* Auto Sync / Refresh */}
          <button
            onClick={triggerAutoSync}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Auto-scan expired and low stock according to store rules"
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

      {/* KPI Stats Overview Cards (Section 9) */}
      <div className={`grid grid-cols-2 ${supportsExpiry ? 'sm:grid-cols-6' : 'sm:grid-cols-4'} gap-3`}>
        <div
          onClick={() => setActiveTab('pending')}
          className={`p-3.5 rounded-xl bg-slate-850/80 border cursor-pointer transition hover:border-indigo-500/40 ${
            activeTab === 'pending' ? 'border-indigo-500 ring-1 ring-indigo-500/30' : 'border-slate-700/60'
          }`}
        >
          <div className="text-[11px] font-semibold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
            <ShoppingCart size={14} /> Total Reorder Items
          </div>
          <div className="text-2xl font-bold text-white mt-1">{summary.total_reorders}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Est: ₹{pendingTotal.toLocaleString()}</div>
        </div>

        <div
          onClick={() => setActiveTab('low_stock')}
          className={`p-3.5 rounded-xl bg-slate-850/80 border cursor-pointer transition hover:border-rose-500/40 ${
            activeTab === 'low_stock' ? 'border-rose-500 ring-1 ring-rose-500/30' : 'border-slate-700/60'
          }`}
        >
          <div className="text-[11px] font-semibold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
            <AlertTriangle size={14} /> Low Stock
          </div>
          <div className="text-2xl font-bold text-white mt-1">{summary.low_stock_count}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Below reorder level</div>
        </div>

        {supportsExpiry && (
          <div
            onClick={() => setActiveTab('expired_stock')}
            className={`p-3.5 rounded-xl bg-slate-850/80 border cursor-pointer transition hover:border-amber-500/40 ${
              activeTab === 'expired_stock' ? 'border-amber-500 ring-1 ring-amber-500/30' : 'border-slate-700/60'
            }`}
          >
            <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
              <Clock size={14} /> Expired Stock
            </div>
            <div className="text-2xl font-bold text-white mt-1">{summary.expired_count}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Replacement candidate</div>
          </div>
        )}

        {supportsExpiry && (
          <div
            onClick={() => setActiveTab('expiring_soon')}
            className={`p-3.5 rounded-xl bg-slate-850/80 border cursor-pointer transition hover:border-yellow-500/40 ${
              activeTab === 'expiring_soon' ? 'border-yellow-500 ring-1 ring-yellow-500/30' : 'border-slate-700/60'
            }`}
          >
            <div className="text-[11px] font-semibold uppercase tracking-wider text-yellow-400 flex items-center gap-1.5">
              <Calendar size={14} /> Expiring Soon
            </div>
            <div className="text-2xl font-bold text-white mt-1">{summary.expiring_soon_count}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Within {capability.expiry_warning_days} days</div>
          </div>
        )}

        <div
          onClick={() => setActiveTab('pending')}
          className="p-3.5 rounded-xl bg-slate-850/80 border border-slate-700/60 hover:border-purple-500/40 cursor-pointer transition"
        >
          <div className="text-[11px] font-semibold uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
            <Plus size={14} /> Manual Reorders
          </div>
          <div className="text-2xl font-bold text-white mt-1">{summary.manual_reorders_count}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Manager additions</div>
        </div>

        <div
          onClick={() => setActiveTab('pending')}
          className="p-3.5 rounded-xl bg-slate-850/80 border border-slate-700/60 hover:border-cyan-500/40 cursor-pointer transition"
        >
          <div className="text-[11px] font-semibold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
            <Truck size={14} /> Partially Received
          </div>
          <div className="text-2xl font-bold text-white mt-1">{summary.partially_received_count}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Partial shipments</div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-700/70 overflow-x-auto space-x-2 scrollbar-none">
        <button
          onClick={() => setActiveTab('pending')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'pending'
              ? 'border-indigo-500 text-indigo-400 font-semibold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShoppingCart size={15} />
          <span>Reorder Stock Table ({summary.total_reorders})</span>
        </button>

        <button
          onClick={() => setActiveTab('low_stock')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'low_stock'
              ? 'border-rose-500 text-rose-400 font-semibold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertTriangle size={15} />
          <span>Low Stock ({summary.low_stock_count})</span>
        </button>

        {supportsExpiry && (
          <button
            onClick={() => setActiveTab('expired_stock')}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
              activeTab === 'expired_stock'
                ? 'border-amber-500 text-amber-400 font-semibold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Clock size={15} />
            <span>Expired Stock ({summary.expired_count})</span>
          </button>
        )}

        {supportsExpiry && (
          <button
            onClick={() => setActiveTab('expiring_soon')}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
              activeTab === 'expiring_soon'
                ? 'border-yellow-500 text-yellow-400 font-semibold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Calendar size={15} />
            <span>Expiring Soon ({summary.expiring_soon_count})</span>
          </button>
        )}

        <button
          onClick={() => setActiveTab('suggested')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'suggested'
              ? 'border-purple-500 text-purple-400 font-semibold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <TrendingUp size={15} />
          <span>Suggested</span>
        </button>

        <button
          onClick={() => setActiveTab('previously_ordered')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'previously_ordered'
              ? 'border-blue-500 text-blue-400 font-semibold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <History size={15} />
          <span>Past Orders</span>
        </button>

        <button
          onClick={() => setActiveTab('completed')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'completed'
              ? 'border-emerald-500 text-emerald-400 font-semibold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileCheck2 size={15} />
          <span>Purchase Orders ({data?.completed_reorders.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition flex items-center gap-2 ${
            activeTab === 'history'
              ? 'border-cyan-500 text-cyan-400 font-semibold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers size={15} />
          <span>Reorder & Receipt History</span>
        </button>
      </div>

      {/* TAB 1: REORDER STOCK TABLE (PENDING BASKET) */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-4 rounded-xl bg-slate-850 border border-slate-700/60 shadow-sm">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <ShoppingCart size={20} className="text-indigo-400" />
                <span>Active Reorder List ({data?.pending_reorders.length || 0})</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Stores replenishment requests. Edit requested quantities with decimals/counts, export clean CSV sheets, or receive arriving stock directly into local inventory.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              {/* Export Selected / All */}
              <button
                onClick={handleExportCSV}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium text-xs transition shadow-sm"
              >
                <Download size={15} />
                <span>Export CSV ({selectedItemIds.length > 0 ? `${selectedItemIds.length} Selected` : 'All'})</span>
              </button>

              {/* Physical Receive Stock Button */}
              <button
                onClick={openReceiveModalForSelected}
                disabled={selectedItemIds.length === 0}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg font-semibold text-xs md:text-sm transition shadow-sm ${
                  selectedItemIds.length > 0
                    ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                }`}
                title="Directly receive real-life arrived stock into local inventory"
              >
                <Truck size={16} />
                <span>Receive Selected into Stock ({selectedItemIds.length})</span>
              </button>

              {/* Create Purchase Order */}
              <button
                onClick={createPurchaseOrder}
                disabled={!data || data.pending_reorders.length === 0}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs md:text-sm transition shadow-lg shadow-indigo-600/20"
              >
                <FileCheck2 size={16} />
                <span>Create PO</span>
              </button>
            </div>
          </div>

          {(!data?.pending_reorders || data.pending_reorders.length === 0) ? (
            <div className="p-12 text-center rounded-xl bg-slate-850 border border-slate-700/60 text-slate-400">
              <CheckCircle2 size={40} className="mx-auto text-emerald-400 mb-2 opacity-80" />
              <p className="font-semibold text-white text-base">No items currently require reordering.</p>
              <p className="text-sm mt-1">Your current stock levels do not require replenishment.</p>
              <button
                onClick={() => {
                  setShowAddModal(true)
                  setSelectedCatalogProduct(null)
                  setDuplicatePrompt(null)
                }}
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition"
              >
                <Plus size={14} />
                <span>+ Add Manual Reorder</span>
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-3 w-10 text-center">
                      <button
                        onClick={toggleSelectAll}
                        className="text-slate-400 hover:text-white transition"
                        title={isAllSelected ? "Deselect all" : "Select all"}
                      >
                        {isAllSelected ? <CheckSquare size={17} className="text-indigo-400" /> : <Square size={17} />}
                      </button>
                    </th>
                    <th className="py-3 px-4">Product Details</th>
                    <th className="py-3 px-4">Current Stock</th>
                    <th className="py-3 px-4">Reorder Level</th>
                    <th className="py-3 px-4">Requested Qty</th>
                    <th className="py-3 px-4">Received / Remaining</th>
                    <th className="py-3 px-4">Unit</th>
                    <th className="py-3 px-4">Supplier</th>
                    <th className="py-3 px-4">Reason</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {data.pending_reorders.map((item) => {
                    const isSelected = selectedItemIds.includes(item.id)
                    const isPartiallyReceived = item.status === 'partially_received'
                    const remainingQty = item.remaining_quantity ?? Math.max(item.selected_quantity - item.received_quantity, 0)

                    return (
                      <tr
                        key={item.id}
                        className={`transition ${isSelected ? 'bg-indigo-950/20' : 'hover:bg-slate-800/40'}`}
                      >
                        <td className="py-3 px-3 text-center">
                          <button
                            onClick={() => toggleSelectItem(item.id)}
                            className="text-slate-400 hover:text-white transition"
                          >
                            {isSelected ? <CheckSquare size={17} className="text-indigo-400" /> : <Square size={17} />}
                          </button>
                        </td>
                        <td className="py-3 px-4">
                          <div className="font-semibold text-white">{item.product_name}</div>
                          <div className="text-xs text-slate-500 font-mono flex flex-wrap items-center gap-2 mt-0.5">
                            <span>SKU: {item.sku}</span>
                            {item.barcode && (
                              <span className="text-indigo-400 flex items-center gap-0.5">
                                <Barcode size={12} /> {item.barcode}
                              </span>
                            )}
                            {/* Clothing variant display */}
                            {isClothing && (item.size || item.color) && (
                              <span className="px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20 text-[10px] font-sans">
                                {item.color ? `${item.color} / ` : ''}{item.size || ''}
                              </span>
                            )}
                            {/* Pack size */}
                            {supportsPackSize && item.pack_size && (
                              <span className="text-slate-400">Pack: {item.pack_size}</span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 font-mono font-medium">
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            item.current_stock <= item.reorder_level
                              ? 'bg-rose-500/10 text-rose-400 font-semibold'
                              : 'text-slate-300'
                          }`}>
                            {item.current_stock}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-400 text-xs">{item.reorder_level}</td>
                        <td className="py-3 px-4">
                          {editingItemId === item.id ? (
                            <div className="flex items-center gap-1.5">
                              <input
                                type="number"
                                step={allowDecimals ? "0.1" : "1"}
                                min={allowDecimals ? "0.1" : "1"}
                                value={editQty}
                                onChange={(e) => setEditQty(Number(e.target.value))}
                                className="w-20 px-2 py-1 rounded bg-slate-900 border border-indigo-500 text-white text-xs font-mono"
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
                              <span className="font-bold text-white text-sm font-mono">{item.selected_quantity}</span>
                              <button
                                onClick={() => {
                                  setEditingItemId(item.id)
                                  setEditQty(item.selected_quantity)
                                }}
                                className="p-1 text-slate-400 hover:text-indigo-400 transition"
                                title="Edit requested quantity"
                              >
                                <Edit2 size={13} />
                              </button>
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {isPartiallyReceived ? (
                            <div>
                              <span className="font-mono text-xs font-bold text-amber-400">
                                {item.received_quantity} received
                              </span>
                              <div className="text-[11px] text-slate-400 font-mono">
                                ({remainingQty} remaining)
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">—</span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono text-xs text-slate-300">
                          {item.unit || capability.default_unit}
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-300">{item.supplier_name}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                            item.source === 'expired_stock' || item.source === 'expired_and_low'
                              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              : item.source === 'manual'
                              ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          }`}>
                            {item.reason || item.source}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase ${
                            item.status === 'received'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : item.status === 'partially_received'
                              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              : item.status === 'ordered'
                              ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                              : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                          }`}>
                            {item.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                          {/* Receive Stock Action */}
                          <button
                            onClick={() => openReceiveModalForSingle(item)}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600 text-emerald-300 hover:text-white border border-emerald-500/30 text-xs font-medium transition"
                            title="Directly receive physical delivery into local stock"
                          >
                            <Truck size={13} />
                            <span>Add to Stock</span>
                          </button>

                          <button
                            onClick={() => removePendingItem(item.id, item.product_name)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition inline-flex items-center"
                            title="Remove from reorder list (does not delete product)"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>

              <div className="p-4 bg-slate-900/60 border-t border-slate-700/60 flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="text-xs text-slate-400">
                  <span>Selected: <strong>{selectedItemIds.length}</strong> of {data.pending_reorders.length} items</span>
                  {selectedItemIds.length > 0 && (
                    <button
                      onClick={() => setSelectedItemIds([])}
                      className="ml-3 text-indigo-400 hover:underline"
                    >
                      Clear Selection
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-4 text-xs">
                  <span className="text-slate-400">Total Estimated Basket Cost:</span>
                  <span className="text-base font-bold text-emerald-400 font-mono">
                    ₹{pendingTotal.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: LOW STOCK CANDIDATES */}
      {activeTab === 'low_stock' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Products Below Reorder Threshold</h2>
              <p className="text-xs text-slate-400">Condition A: Current Stock ≤ Reorder Level</p>
            </div>
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
                    <th className="py-3 px-4">Product Details</th>
                    <th className="py-3 px-4">Current Stock</th>
                    <th className="py-3 px-4">Reorder Level</th>
                    <th className="py-3 px-4">Unit</th>
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
                        <div className="text-xs text-slate-500 font-mono flex flex-wrap items-center gap-2 mt-0.5">
                          <span>{item.sku}</span>
                          {item.barcode && (
                            <span className="text-indigo-400 flex items-center gap-0.5">
                              <Barcode size={12} /> {item.barcode}
                            </span>
                          )}
                          {isClothing && (item.size || item.color) && (
                            <span className="px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-300 text-[10px]">
                              {item.color ? `${item.color} / ` : ''}{item.size || ''}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          {item.current_stock}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-300">{item.reorder_level}</td>
                      <td className="py-3 px-4 text-xs font-mono">{item.unit || capability.default_unit}</td>
                      <td className="py-3 px-4 text-xs">
                        {item.last_order_quantity ? (
                          <div>
                            <span className="font-semibold text-white">{item.last_order_quantity} {item.unit || 'units'}</span>
                            <div className="text-slate-500">{item.last_order_date || 'Past order'}</div>
                          </div>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-300">{item.supplier_name}</td>
                      <td className="py-3 px-4 font-semibold text-emerald-400">
                        {item.suggested_quantity} {item.unit || 'units'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => addToReorder(item, item.suggested_quantity, `Low stock: ${item.current_stock} remaining`)}
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

      {/* TAB 3: EXPIRED STOCK (ONLY FOR PERTINENT BUSINESS TYPES) */}
      {supportsExpiry && activeTab === 'expired_stock' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Clock size={18} className="text-amber-400" />
                <span>Expired Stock Batches Requiring Reorder</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Condition B: Inventory batches where Expiry Date ≤ Current Date. Reorders replenishment without deleting stock.
              </p>
            </div>
          </div>

          {(!data?.expired_stock || data.expired_stock.length === 0) ? (
            <div className="p-12 text-center rounded-xl bg-slate-850 border border-slate-700/60 text-slate-400">
              <CheckCircle2 size={36} className="mx-auto text-emerald-400 mb-2 opacity-80" />
              <p className="font-medium text-white">No expired stock detected in store batches.</p>
              <p className="text-sm mt-1">All current inventory batches are active and within safe shelf life dates.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">Product Details</th>
                    <th className="py-3 px-4">Expired Units</th>
                    <th className="py-3 px-4">Earliest Expiry</th>
                    <th className="py-3 px-4">Expired Batches</th>
                    <th className="py-3 px-4">Supplier</th>
                    <th className="py-3 px-4">Suggested Reorder</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {data.expired_stock.map((item) => (
                    <tr key={item.product_id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4">
                        <div className="font-medium text-white">{item.product_name}</div>
                        <div className="text-xs text-slate-500 font-mono flex items-center gap-2 mt-0.5">
                          <span>{item.sku}</span>
                          {item.barcode && <span className="text-indigo-400 flex items-center gap-0.5"><Barcode size={12} /> {item.barcode}</span>}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          {item.expired_quantity || 0} {item.unit || 'units'} expired
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs font-mono text-rose-400">
                        {item.earliest_expiry || 'Expired'}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-300">{item.expired_batches_count || 1} batch(es)</td>
                      <td className="py-3 px-4 text-xs text-slate-300">{item.supplier_name}</td>
                      <td className="py-3 px-4 font-semibold text-emerald-400">
                        {item.suggested_quantity} {item.unit || 'units'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => addToReorder(item, item.suggested_quantity, `Expired stock replacement: ${item.expired_quantity} ${item.unit || 'units'}`)}
                          disabled={busyItem === item.product_id}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs transition shadow-sm"
                        >
                          <Plus size={14} />
                          <span>Reorder Replacement</span>
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

      {/* TAB 4: EXPIRING SOON (WARNING PERIOD SUPPORT) */}
      {supportsExpiry && activeTab === 'expiring_soon' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Calendar size={18} className="text-yellow-400" />
                <span>Expiring Soon Products (Next {capability.expiry_warning_days} Days)</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Configurable warning window enables proactive replenishment orders before stock expires on the shelf.
              </p>
            </div>
          </div>

          {(!data?.expiring_soon_stock || data.expiring_soon_stock.length === 0) ? (
            <div className="p-12 text-center rounded-xl bg-slate-850 border border-slate-700/60 text-slate-400">
              <CheckCircle2 size={36} className="mx-auto text-emerald-400 mb-2 opacity-80" />
              <p className="font-medium text-white">No batches expiring within {capability.expiry_warning_days} days.</p>
              <p className="text-sm mt-1">Inventory freshness is well within normal thresholds.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">Product Details</th>
                    <th className="py-3 px-4">Expiring Qty</th>
                    <th className="py-3 px-4">Expiry Date</th>
                    <th className="py-3 px-4">Current Stock</th>
                    <th className="py-3 px-4">Supplier</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {data.expiring_soon_stock.map((item) => (
                    <tr key={item.product_id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4">
                        <div className="font-medium text-white">{item.product_name}</div>
                        <div className="text-xs text-slate-500 font-mono">{item.sku}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                          {item.expiring_quantity || 0} {item.unit || 'units'}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-yellow-300 text-xs">{item.earliest_expiry}</td>
                      <td className="py-3 px-4 font-mono text-slate-300">{item.current_stock}</td>
                      <td className="py-3 px-4 text-xs text-slate-400">{item.supplier_name}</td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => addToReorder(item, item.suggested_quantity, `Expiring soon warning (${item.earliest_expiry})`)}
                          disabled={busyItem === item.product_id}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-yellow-600 hover:bg-yellow-500 text-white font-medium text-xs transition shadow-sm"
                        >
                          <Plus size={14} />
                          <span>Reorder Proactively</span>
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

      {/* TAB 5: SUGGESTED REORDERS */}
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
                      <div className="text-sm font-bold text-white mt-0.5">{item.current_stock} {item.unit || ''}</div>
                    </div>
                    <div>
                      <div className="text-slate-400">Reorder Level</div>
                      <div className="text-sm font-bold text-white mt-0.5">{item.reorder_level} {item.unit || ''}</div>
                    </div>
                    <div>
                      <div className="text-slate-400">Suggested</div>
                      <div className="text-sm font-bold text-emerald-400 mt-0.5">{item.suggested_quantity} {item.unit || ''}</div>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-700/50 flex items-center justify-between">
                  <span className="text-xs text-slate-400">Last order: {item.last_order_quantity || 15} {item.unit || 'units'}</span>
                  <button
                    onClick={() => addToReorder(item, item.suggested_quantity, item.reason)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition"
                  >
                    <Plus size={14} />
                    <span>Add to Reorder</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 6: PAST ORDERS */}
      {activeTab === 'previously_ordered' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Repeat Previous Purchases</h2>
            <span className="text-xs text-slate-400">Quickly re-order goods from verified historical invoices</span>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                <tr>
                  <th className="py-3 px-4">Product</th>
                  <th className="py-3 px-4">Supplier</th>
                  <th className="py-3 px-4">Last Price</th>
                  <th className="py-3 px-4">Last Quantity</th>
                  <th className="py-3 px-4">Last Order Date</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60">
                {data?.previously_ordered.map((item) => (
                  <tr key={item.product_id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4">
                      <div className="font-medium text-white">{item.product_name}</div>
                      <div className="text-xs text-slate-500 font-mono">{item.sku}</div>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-300">{item.supplier_name}</td>
                    <td className="py-3 px-4 font-mono text-xs">₹{item.previous_price}</td>
                    <td className="py-3 px-4 font-semibold text-white">{item.last_order_quantity} {item.unit || ''}</td>
                    <td className="py-3 px-4 text-xs text-slate-400">{item.last_order_date || 'Recent'}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => addToReorder(item, item.last_order_quantity, 'Repeat previous purchase order')}
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
        </div>
      )}

      {/* TAB 7: PURCHASE ORDERS */}
      {activeTab === 'completed' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Generated Purchase Orders</h2>
            <span className="text-xs text-slate-400">Formal purchase orders sent to suppliers</span>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                <tr>
                  <th className="py-3 px-4">PO Number</th>
                  <th className="py-3 px-4">Supplier</th>
                  <th className="py-3 px-4">Items</th>
                  <th className="py-3 px-4">Total Amount</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Created Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60">
                {data?.completed_reorders.map((po) => (
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
        </div>
      )}

      {/* TAB 8: AUDIT HISTORY (SECTIONS 29 & 50) */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setHistorySubTab('reorders')}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                  historySubTab === 'reorders'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                Reorder Requests History
              </button>
              <button
                onClick={() => setHistorySubTab('receipts')}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                  historySubTab === 'receipts'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                Stock Receiving Audit Log ({data?.receiving_history?.length || 0})
              </button>
            </div>

            <div className="relative w-64">
              <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                placeholder="Search history by name, SKU, batch..."
                className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          {historySubTab === 'reorders' ? (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-800/80 text-[11px] uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-2.5 px-3">Product Name</th>
                    <th className="py-2.5 px-3">SKU / Barcode</th>
                    <th className="py-2.5 px-3">Requested</th>
                    <th className="py-2.5 px-3">Received</th>
                    <th className="py-2.5 px-3">Supplier</th>
                    <th className="py-2.5 px-3">Reason</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {filteredReorderHistory.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-semibold text-white">{item.product_name}</td>
                      <td className="py-2.5 px-3 font-mono text-slate-400">{item.sku}</td>
                      <td className="py-2.5 px-3 font-bold text-white font-mono">{item.selected_quantity} {item.unit}</td>
                      <td className="py-2.5 px-3 font-mono text-emerald-400">{item.received_quantity} {item.unit}</td>
                      <td className="py-2.5 px-3 text-slate-300">{item.supplier_name}</td>
                      <td className="py-2.5 px-3 text-slate-400">{item.reason || item.source}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300 uppercase">
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-800/80 text-[11px] uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-2.5 px-3">Receipt / Tx Ref</th>
                    <th className="py-2.5 px-3">Product Name</th>
                    <th className="py-2.5 px-3">Stock Before</th>
                    <th className="py-2.5 px-3">Received Qty</th>
                    <th className="py-2.5 px-3">Stock After</th>
                    <th className="py-2.5 px-3">Batch / Lot</th>
                    <th className="py-2.5 px-3">Serial No</th>
                    <th className="py-2.5 px-3">Received By</th>
                    <th className="py-2.5 px-3">Date & Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {filteredReceiptHistory.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-mono text-indigo-400 font-semibold">{item.transaction_id || `TX-${item.id}`}</td>
                      <td className="py-2.5 px-3 font-semibold text-white">
                        {item.product_name}
                        {item.size && <span className="ml-1 text-[10px] text-purple-300">({item.size})</span>}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-400">{item.previous_stock}</td>
                      <td className="py-2.5 px-3 font-mono font-bold text-emerald-400">+{item.received_quantity} {item.unit}</td>
                      <td className="py-2.5 px-3 font-mono text-white font-semibold">{item.new_stock}</td>
                      <td className="py-2.5 px-3 font-mono text-slate-400">{item.lot_number || '—'}</td>
                      <td className="py-2.5 px-3 font-mono text-amber-400">{item.serial_number || '—'}</td>
                      <td className="py-2.5 px-3 text-slate-400">{item.performed_by}</td>
                      <td className="py-2.5 px-3 text-slate-500 font-mono text-[11px]">
                        {item.received_at ? new Date(item.received_at).toLocaleString() : 'Recent'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* MODAL 1: ADD PRODUCT MANUALLY (WITH DUPLICATE PROTECTION - SECTION 51) */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl animate-fadeIn">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Plus size={18} className="text-indigo-400" />
                <span>Add Product to Reorder Basket</span>
              </h3>
              <button
                onClick={() => {
                  setShowAddModal(false)
                  setSelectedCatalogProduct(null)
                  setDuplicatePrompt(null)
                  setSearchQuery('')
                  setSearchResults([])
                }}
                className="text-slate-400 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>

            {/* DUPLICATE PROMPT INTERACTIVE BANNER */}
            {duplicatePrompt && (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 space-y-3">
                <div className="flex items-start gap-2">
                  <AlertCircle size={18} className="text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-bold text-white text-sm">Already in active reorder list!</div>
                    <p className="text-xs text-amber-200/80 mt-1">
                      "{duplicatePrompt.product_name}" is already pending with requested quantity: <strong>{duplicatePrompt.current_requested_quantity}</strong>.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-amber-500/20 text-xs">
                  <button
                    onClick={() => handleManualAddSubmit('increase')}
                    className="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold transition"
                  >
                    Increase Quantity (+{duplicatePrompt.new_quantity})
                  </button>
                  <button
                    onClick={() => handleManualAddSubmit('replace')}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition"
                  >
                    Set to {duplicatePrompt.new_quantity}
                  </button>
                  <button
                    onClick={() => setDuplicatePrompt(null)}
                    className="px-3 py-1.5 text-slate-400 hover:text-white transition"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {!duplicatePrompt && (
              <>
                {/* Catalog Search Input */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-300">Search Store Catalog (Name, SKU, Barcode, Variant)</label>
                  <div className="relative">
                    <Search size={16} className="absolute left-3 top-3 text-slate-400" />
                    <input
                      type="text"
                      placeholder={`e.g. ${isClothing ? 'T-Shirt, Black M...' : 'Flour, Paracetamol, Pen...'}`}
                      value={searchQuery}
                      onChange={(e) => searchCatalog(e.target.value)}
                      className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-500 text-sm focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                </div>

                {searchingCatalog && (
                  <div className="text-xs text-slate-400 text-center py-2">Searching store catalog…</div>
                )}

                {searchResults.length > 0 && !selectedCatalogProduct && (
                  <div className="max-h-48 overflow-y-auto rounded-xl border border-slate-700/60 divide-y divide-slate-800 bg-slate-850">
                    {searchResults.map((item) => (
                      <div
                        key={item.product_id}
                        onClick={() => {
                          setSelectedCatalogProduct(item)
                          const target = item.target_stock && item.target_stock > 0 ? item.target_stock : item.reorder_level * 2
                          setManualAddQty(Math.max(target - item.current_stock, allowDecimals ? 1.0 : 1))
                        }}
                        className="p-3 hover:bg-indigo-600/10 cursor-pointer flex items-center justify-between transition"
                      >
                        <div>
                          <div className="text-sm font-semibold text-white flex items-center gap-2">
                            <span>{item.product_name}</span>
                            {isClothing && (item.size || item.color) && (
                              <span className="px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-300 text-[10px]">
                                {item.color} {item.size}
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-slate-400 font-mono flex items-center gap-2 mt-0.5">
                            <span>SKU: {item.sku}</span>
                            {item.barcode && <span className="text-indigo-400">BAR: {item.barcode}</span>}
                          </div>
                        </div>
                        <div className="text-right text-xs">
                          <div className="text-slate-300">Stock: <strong className="text-white">{item.current_stock}</strong> {item.unit || ''}</div>
                          <div className="text-emerald-400 font-mono">₹{item.purchase_price}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {selectedCatalogProduct && (
                  <div className="p-3.5 rounded-xl bg-indigo-950/40 border border-indigo-500/30 space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-bold text-white text-sm">{selectedCatalogProduct.product_name}</div>
                        <div className="text-xs text-slate-400 font-mono">
                          Current Stock: {selectedCatalogProduct.current_stock} {selectedCatalogProduct.unit || 'units'} | Reorder Level: {selectedCatalogProduct.reorder_level}
                        </div>
                      </div>
                      <button
                        onClick={() => setSelectedCatalogProduct(null)}
                        className="text-xs text-indigo-400 hover:underline"
                      >
                        Change Product
                      </button>
                    </div>

                    <div className="grid grid-cols-2 gap-3 pt-2 border-t border-indigo-500/20">
                      <div>
                        <label className="text-xs text-slate-300 block mb-1">
                          Requested Quantity ({selectedCatalogProduct.unit || capability.default_unit})
                        </label>
                        <input
                          type="number"
                          step={allowDecimals ? "0.1" : "1"}
                          min={allowDecimals ? "0.1" : "1"}
                          value={manualAddQty}
                          onChange={(e) => setManualAddQty(Math.max(allowDecimals ? 0.1 : 1, Number(e.target.value)))}
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-indigo-500/50 text-white font-mono text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-slate-300 block mb-1">Reason / Notes</label>
                        <input
                          type="text"
                          value={manualAddReason}
                          onChange={(e) => setManualAddReason(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-white text-xs"
                          placeholder="e.g. Expected weekend demand"
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                  <button
                    onClick={() => {
                      setShowAddModal(false)
                      setSelectedCatalogProduct(null)
                    }}
                    className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleManualAddSubmit('prompt')}
                    disabled={!selectedCatalogProduct}
                    className={`px-4 py-2 rounded-xl font-semibold text-sm transition ${
                      selectedCatalogProduct
                        ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20'
                        : 'bg-slate-800 text-slate-600 cursor-not-allowed'
                    }`}
                  >
                    Add to Reorder Basket
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* MODAL 2: PHYSICAL STOCK ARRIVAL / STOCK RECEIVING MODAL (SECTIONS 21-28) */}
      {showReceiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl p-6 space-y-5 shadow-2xl my-8">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <Truck size={22} className="text-emerald-400" />
                  <span>Receive Stock into Local Inventory</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Enter actual delivered quantities (never assumes requested == received). Supports partial delivery and business attributes.
                </p>
              </div>
              <button onClick={() => setShowReceiveModal(false)} className="text-slate-400 hover:text-white">
                <X size={20} />
              </button>
            </div>

            {/* General Note */}
            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1">Receiving Delivery Reference / Note</label>
              <input
                type="text"
                value={generalReceiveNote}
                onChange={(e) => setGeneralReceiveNote(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm"
                placeholder="e.g. Shipment delivered via BlueDart Courier, verified by store manager"
              />
            </div>

            {/* Editable Items Table */}
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850 max-h-96">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-800/80 text-[11px] uppercase text-slate-400 border-b border-slate-700 sticky top-0 z-10">
                  <tr>
                    <th className="py-2.5 px-3">Product</th>
                    <th className="py-2.5 px-3">Requested</th>
                    <th className="py-2.5 px-3">Received Qty</th>
                    <th className="py-2.5 px-3">Delivery Status</th>
                    {supportsBatch && <th className="py-2.5 px-3">Batch / Lot #</th>}
                    {supportsSerial && <th className="py-2.5 px-3">Serial Number</th>}
                    {supportsExpiry && <th className="py-2.5 px-3">Expiry Date</th>}
                    <th className="py-2.5 px-3">Cost Price (₹)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {receiveItemsList.map((item, idx) => {
                    const isPartial = item.received_quantity < item.requested_quantity
                    const remaining = Math.max(item.requested_quantity - (item.already_received + item.received_quantity), 0)

                    return (
                      <tr key={idx} className="hover:bg-slate-800/40">
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-white text-xs">{item.product_name}</div>
                          <div className="text-[11px] text-slate-500 font-mono flex items-center gap-1.5">
                            <span>{item.sku}</span>
                            {item.size && <span className="text-purple-300">({item.color} {item.size})</span>}
                          </div>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-300">
                          {item.requested_quantity} {item.unit}
                        </td>
                        <td className="py-2.5 px-3">
                          <input
                            type="number"
                            step={allowDecimals ? "0.1" : "1"}
                            min="0.1"
                            value={item.received_quantity}
                            onChange={(e) => {
                              const val = Math.max(0.1, Number(e.target.value))
                              setReceiveItemsList(prev => prev.map((it, i) => i === idx ? { ...it, received_quantity: val } : it))
                            }}
                            className="w-20 px-2 py-1 rounded bg-slate-900 border border-indigo-500 text-white font-mono text-xs font-bold"
                          />
                        </td>
                        <td className="py-2.5 px-3">
                          {isPartial ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                              Partial ({remaining} remaining)
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              Full Delivery
                            </span>
                          )}
                        </td>
                        {supportsBatch && (
                          <td className="py-2.5 px-3">
                            <input
                              type="text"
                              value={item.batch_number}
                              onChange={(e) => {
                                const val = e.target.value
                                setReceiveItemsList(prev => prev.map((it, i) => i === idx ? { ...it, batch_number: val } : it))
                              }}
                              className="w-28 px-2 py-1 rounded bg-slate-900 border border-slate-700 text-white font-mono text-xs"
                              placeholder="LOT-XXX"
                            />
                          </td>
                        )}
                        {supportsSerial && (
                          <td className="py-2.5 px-3">
                            <input
                              type="text"
                              value={item.serial_number}
                              onChange={(e) => {
                                const val = e.target.value
                                setReceiveItemsList(prev => prev.map((it, i) => i === idx ? { ...it, serial_number: val } : it))
                              }}
                              className="w-28 px-2 py-1 rounded bg-slate-900 border border-slate-700 text-white font-mono text-xs"
                              placeholder="SN-12345"
                            />
                          </td>
                        )}
                        {supportsExpiry && (
                          <td className="py-2.5 px-3">
                            <input
                              type="date"
                              value={item.expiry_date}
                              onChange={(e) => {
                                const val = e.target.value
                                setReceiveItemsList(prev => prev.map((it, i) => i === idx ? { ...it, expiry_date: val } : it))
                              }}
                              className="w-32 px-2 py-1 rounded bg-slate-900 border border-slate-700 text-white text-xs"
                            />
                          </td>
                        )}
                        <td className="py-2.5 px-3">
                          <input
                            type="number"
                            step="0.01"
                            value={item.purchase_price}
                            onChange={(e) => {
                              const val = Number(e.target.value)
                              setReceiveItemsList(prev => prev.map((it, i) => i === idx ? { ...it, purchase_price: val } : it))
                            }}
                            className="w-20 px-2 py-1 rounded bg-slate-900 border border-slate-700 text-white font-mono text-xs"
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="pt-3 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="text-xs text-slate-400">
                Total Products: <strong className="text-white">{receiveItemsList.length}</strong> | Total Units to Add:{' '}
                <strong className="text-emerald-400 font-mono">
                  {receiveItemsList.reduce((acc, curr) => acc + (curr.received_quantity || 0), 0)}
                </strong>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowReceiveModal(false)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmReceiveStock}
                  disabled={receivingSubmitting || receiveItemsList.length === 0}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition shadow-lg shadow-emerald-600/20 flex items-center gap-2"
                >
                  {receivingSubmitting ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                  <span>Confirm Receipt & Update Stock</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: WHOLESALER DOCUMENT INGESTION (SECTIONS 30-40, 52, 59) */}
      {showWholesalerModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-5xl p-6 space-y-5 shadow-2xl my-8">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <UploadCloud size={22} className="text-blue-400" />
                  <span>Import Supplier / Wholesaler Delivery File</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Upload delivery files (CSV, Excel, PDF, Images). Uses strict matching priority (Barcode &gt; SKU &gt; Serial &gt; Variant &gt; Name). Review before confirming stock.
                </p>
              </div>
              <button
                onClick={() => {
                  setShowWholesalerModal(false)
                  setWholesalerData(null)
                  setWholesalerFile(null)
                }}
                className="text-slate-400 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>

            {/* DUPLICATE DELIVERY WARNING (SECTION 52) */}
            {wholesalerData?.duplicate_delivery_warning && (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-2">
                <AlertTriangle size={18} className="text-amber-400 shrink-0" />
                <span>{wholesalerData.duplicate_delivery_warning}</span>
              </div>
            )}

            {/* Upload Zone */}
            {!wholesalerData && (
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-700 hover:border-blue-500 rounded-2xl p-8 text-center cursor-pointer bg-slate-850/50 hover:bg-slate-800/40 transition group"
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  accept=".csv,.xlsx,.xls,.pdf,.png,.jpg,.jpeg,.webp,.txt,.json"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleWholesalerFileUpload(e.target.files[0])
                    }
                  }}
                />
                <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mx-auto mb-3 group-hover:scale-105 transition">
                  <UploadCloud size={24} />
                </div>
                <p className="font-semibold text-white text-base">Click to upload supplier delivery file</p>
                <p className="text-xs text-slate-400 mt-1">
                  Supports CSV, XLSX, XLS, PDF, PNG, JPG, and JSON
                </p>
                {wholesalerUploading && (
                  <div className="mt-4 flex items-center justify-center gap-2 text-sm text-blue-400">
                    <RefreshCw size={16} className="animate-spin" />
                    <span>Extracting line items, preserving barcodes &amp; serials, and matching catalog…</span>
                  </div>
                )}
              </div>
            )}

            {/* Extracted Wholesaler Data Preview */}
            {wholesalerData && (
              <div className="space-y-4">
                {/* Invoice and Summary Bar (Section 59) */}
                <div className="p-4 rounded-xl bg-slate-850 border border-slate-700/60 flex flex-wrap items-center justify-between gap-4 text-xs">
                  <div>
                    <span className="text-slate-400">Supplier: </span>
                    <strong className="text-white text-sm">{wholesalerData.supplier_name}</strong>
                    <span className="mx-2 text-slate-600">|</span>
                    <span className="text-slate-400">Invoice: </span>
                    <strong className="text-white font-mono">{wholesalerData.invoice_number}</strong>
                  </div>

                  {wholesalerData.summary && (
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300">
                        Total Rows: <strong>{wholesalerData.summary.total_rows}</strong>
                      </span>
                      <span className="px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Matched: <strong>{wholesalerData.summary.matched}</strong>
                      </span>
                      {wholesalerData.summary.needs_review > 0 && (
                        <span className="px-2.5 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          Needs Review: <strong>{wholesalerData.summary.needs_review}</strong>
                        </span>
                      )}
                      {wholesalerData.summary.invalid > 0 && (
                        <span className="px-2.5 py-1 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          Invalid: <strong>{wholesalerData.summary.invalid}</strong>
                        </span>
                      )}
                    </div>
                  )}

                  <button
                    onClick={() => {
                      setWholesalerData(null)
                      setWholesalerFile(null)
                    }}
                    className="text-xs text-blue-400 hover:underline"
                  >
                    Upload Different File
                  </button>
                </div>

                {/* Review Table (Section 37) */}
                <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850 max-h-80">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-800/80 text-[11px] uppercase text-slate-400 border-b border-slate-700 sticky top-0 z-10">
                      <tr>
                        <th className="py-2.5 px-3">Imported Item</th>
                        <th className="py-2.5 px-3">Matched Catalog Product</th>
                        <th className="py-2.5 px-3">Quantity</th>
                        <th className="py-2.5 px-3">Barcode</th>
                        <th className="py-2.5 px-3">Serial / Batch</th>
                        {supportsExpiry && <th className="py-2.5 px-3">Expiry</th>}
                        <th className="py-2.5 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {wholesalerData.items.map((item, idx) => {
                        const isReview = item.status === 'needs_review'
                        const isMatched = item.status === 'matched'
                        const isNotFound = item.status === 'not_found'

                        return (
                          <tr key={idx} className="hover:bg-slate-800/40">
                            <td className="py-2.5 px-3">
                              <div className="font-semibold text-white">{item.raw_product_name}</div>
                              {item.size && (
                                <div className="text-[10px] text-purple-300">Variant: {item.color} {item.size}</div>
                              )}
                              {item.error_message && (
                                <div className="text-[10px] text-rose-400">{item.error_message}</div>
                              )}
                            </td>
                            <td className="py-2.5 px-3">
                              {isReview && item.candidates && item.candidates.length > 0 ? (
                                <div className="space-y-1">
                                  <div className="text-[10px] text-amber-400 font-semibold">Multiple Matches - Select One:</div>
                                  <select
                                    onChange={(e) => {
                                      const cand = item.candidates?.find(c => c.product_id === Number(e.target.value))
                                      if (cand) handleSelectCandidate(idx, cand)
                                    }}
                                    className="bg-slate-900 border border-amber-500/60 rounded px-2 py-1 text-xs text-white max-w-xs"
                                    defaultValue=""
                                  >
                                    <option value="" disabled>Choose matching product…</option>
                                    {item.candidates.map(c => (
                                      <option key={c.product_id} value={c.product_id}>
                                        {c.product_name} {c.size ? `(${c.size})` : ''} - Match score: {Math.round(c.score * 100)}%
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              ) : isMatched ? (
                                <div>
                                  <span className="font-semibold text-emerald-400">{item.matched_product_name}</span>
                                </div>
                              ) : isNotFound ? (
                                <span className="text-slate-400 italic">Not Found in Catalog</span>
                              ) : (
                                <span className="text-slate-500">—</span>
                              )}
                            </td>
                            <td className="py-2.5 px-3 font-mono font-bold text-white">
                              {item.quantity} {item.unit || ''}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-indigo-400">
                              {item.barcode ? <span className="flex items-center gap-1"><Barcode size={13} /> {item.barcode}</span> : '—'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-300">
                              {item.serial_number ? `SN: ${item.serial_number}` : item.batch_number ? `Lot: ${item.batch_number}` : '—'}
                            </td>
                            {supportsExpiry && (
                              <td className="py-2.5 px-3 text-slate-400 font-mono">
                                {item.expiry_date || '—'}
                              </td>
                            )}
                            <td className="py-2.5 px-3">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                                isMatched
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : isReview
                                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                  : isNotFound
                                  ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              }`}>
                                {item.status?.replace('_', ' ') || 'Unknown'}
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="pt-3 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3">
                  <div className="text-xs text-slate-400">
                    Ready to Add into Stock:{' '}
                    <strong className="text-emerald-400 font-mono text-sm">
                      {wholesalerData.items.filter(i => i.status === 'matched').length} items
                    </strong>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setShowWholesalerModal(false)
                        setWholesalerData(null)
                      }}
                      className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleConfirmWholesalerIntoStock}
                      disabled={wholesalerConfirming || wholesalerData.items.filter(i => i.status === 'matched').length === 0}
                      className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition shadow-lg shadow-emerald-600/20 flex items-center gap-2"
                    >
                      {wholesalerConfirming ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                      <span>Confirm &amp; Add Directly to Stock</span>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
