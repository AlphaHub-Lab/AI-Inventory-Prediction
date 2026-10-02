import React, { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  Camera,
  CheckCircle2,
  Clock,
  Download,
  Edit2,
  FileCheck2,
  FileText,
  HelpCircle,
  Info,
  Layers,
  Package,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  X
} from 'lucide-react'
import { api, getToken } from '../lib/api'
import type { ReceiptImport, ReceiptItem, User } from '../types'

export default function ReceiptsPage({ currentUser }: { currentUser: User }) {
  const [imports, setImports] = useState<ReceiptImport[]>([])
  const [activeImport, setActiveImport] = useState<ReceiptImport | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [activeView, setActiveView] = useState<'upload' | 'review' | 'history'>('upload')

  // Review screen editable states
  const [supplierName, setSupplierName] = useState('')
  const [supplierGstin, setSupplierGstin] = useState('')
  const [invoiceNumber, setInvoiceNumber] = useState('')
  const [invoiceDate, setInvoiceDate] = useState('')
  const [items, setItems] = useState<ReceiptItem[]>([])

  const fileInputRef = useRef<HTMLInputElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)

  async function fetchReceipts() {
    setLoading(true)
    setError(null)
    try {
      const res = await api<ReceiptImport[]>('/api/receipts')
      setImports(res)
      // If there's an import requiring review, load it automatically
      const pending = res.find((r) => r.processing_status === 'review_required')
      if (pending && !activeImport) {
        loadReceiptDetail(pending.id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch receipts')
    } finally {
      setLoading(false)
    }
  }

  async function loadReceiptDetail(id: number) {
    setLoading(true)
    try {
      const res = await api<ReceiptImport>(`/api/receipts/${id}`)
      setActiveImport(res)
      setSupplierName(res.supplier_name || 'Vendor')
      setInvoiceNumber(res.invoice_number || `INV-${res.id}`)
      setInvoiceDate(res.invoice_date || new Date().toISOString().split('T')[0])
      setItems(res.items || [])
      setActiveView('review')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load receipt details')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchReceipts()
  }, [])

  async function handleFileUpload(file: File) {
    setUploading(true)
    setError(null)
    setSuccessMsg(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const token = getToken()
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const response = await fetch('/api/receipts/upload', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: formData
      })

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}))
        throw new Error(errJson.error?.message || errJson.detail || 'Upload failed')
      }

      const result = await response.json()
      setSuccessMsg(`Receipt "${file.name}" uploaded and extracted successfully! Please review items below.`)

      // Load into review state
      await loadReceiptDetail(result.import_id)
      await fetchReceipts()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error uploading receipt file')
    } finally {
      setUploading(false)
    }
  }

  function handleFileDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0])
    }
  }

  function updateItem(index: number, field: keyof ReceiptItem, value: any) {
    setItems((prev) => {
      const copy = [...prev]
      copy[index] = { ...copy[index], [field]: value }
      return copy
    })
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, idx) => idx !== index))
  }

  function addNewItem() {
    setItems((prev) => [
      ...prev,
      {
        raw_product_name: 'New Item',
        quantity: 1,
        unit: 'unit',
        purchase_price: 10,
        mrp: 15,
        gst_percentage: 5,
        batch_number: `LOT-${Date.now().toString().slice(-6)}`,
        expiry_date: null,
        confidence_score: 100,
        confidence_level: 'HIGH',
        review_status: 'verified',
        match_source: 'new_unmatched'
      }
    ])
  }

  async function handleConfirmImport() {
    if (!activeImport) return
    setConfirming(true)
    setError(null)

    try {
      const payload = {
        supplier_name: supplierName,
        supplier_gstin: supplierGstin,
        invoice_number: invoiceNumber,
        invoice_date: invoiceDate,
        items: items
      }

      const res = await api<{ message: string; items_imported: number }>(
        `/api/receipts/${activeImport.id}/confirm`,
        {
          method: 'POST',
          body: JSON.stringify(payload)
        }
      )

      setSuccessMsg(`Success! ${res.message} Local inventory updated atomically.`)
      setActiveImport(null)
      setActiveView('history')
      await fetchReceipts()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to confirm receipt import')
    } finally {
      setConfirming(false)
    }
  }

  const computedSubtotal = items.reduce((sum, i) => sum + (Number(i.quantity) || 0) * (Number(i.purchase_price) || 0), 0)
  const computedGst = items.reduce(
    (sum, i) => sum + (Number(i.quantity) || 0) * (Number(i.purchase_price) || 0) * ((Number(i.gst_percentage) || 0) / 100),
    0
  )
  const computedGrandTotal = computedSubtotal + computedGst

  return (
    <div className="receipts-page space-y-6 p-4 md:p-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-700/60 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <FileCheck2 size={22} />
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white">AI Receipt & Invoice Ingestion Studio</h1>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Automated OCR extraction, Local/Master catalog fuzzy matching, human verification, and atomic inventory update.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveView('upload')}
            className={`px-3.5 py-2 rounded-lg text-sm font-medium transition flex items-center gap-1.5 ${
              activeView === 'upload'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <Upload size={16} />
            <span>Upload Receipt</span>
          </button>

          {activeImport && (
            <button
              onClick={() => setActiveView('review')}
              className={`px-3.5 py-2 rounded-lg text-sm font-medium transition flex items-center gap-1.5 ${
                activeView === 'review'
                  ? 'bg-amber-600 text-white shadow-md'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              <FileText size={16} />
              <span>Review Screen</span>
            </button>
          )}

          <button
            onClick={() => setActiveView('history')}
            className={`px-3.5 py-2 rounded-lg text-sm font-medium transition flex items-center gap-1.5 ${
              activeView === 'history'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <Clock size={16} />
            <span>Receipt History</span>
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={18} className="text-emerald-400" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-xs text-emerald-400 hover:underline">Dismiss</button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-2">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* VIEW 1: UPLOAD AREA */}
      {activeView === 'upload' && (
        <div className="space-y-6">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleFileDrop}
            className="border-2 border-dashed border-slate-700/80 hover:border-indigo-500/60 rounded-2xl p-10 text-center bg-slate-850/60 hover:bg-slate-850 transition flex flex-col items-center justify-center space-y-4"
          >
            <div className="p-4 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Upload size={36} />
            </div>

            <div className="space-y-1">
              <h3 className="text-lg font-semibold text-white">Upload Purchase Receipt or Supplier Invoice</h3>
              <p className="text-sm text-slate-400 max-w-md mx-auto">
                Drag and drop your receipt image (JPG, PNG, WEBP) or PDF invoice here, or browse files from your device.
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition shadow-lg shadow-indigo-600/25 flex items-center gap-2"
              >
                <FileText size={17} />
                <span>{uploading ? 'Processing OCR…' : 'Select Invoice File'}</span>
              </button>

              <button
                type="button"
                onClick={() => cameraInputRef.current?.click()}
                disabled={uploading}
                className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium text-sm transition flex items-center gap-2"
              >
                <Camera size={17} />
                <span>Camera Capture</span>
              </button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileUpload(e.target.files[0])
                }
              }}
            />

            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileUpload(e.target.files[0])
                }
              }}
            />

            <div className="text-xs text-slate-500 flex items-center gap-3 pt-2">
              <span>Max file size: 15MB</span>
              <span>•</span>
              <span>Magic byte verified</span>
              <span>•</span>
              <span>Encrypted server storage</span>
            </div>
          </div>

          {/* Quick Guidance Box */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-slate-850 border border-slate-700/60">
              <div className="text-sm font-semibold text-white flex items-center gap-2">
                <span className="p-1 rounded bg-indigo-500/20 text-indigo-400">1</span>
                AI Text & Field Extraction
              </div>
              <p className="text-xs text-slate-400 mt-2">
                The optical recognition pipeline extracts vendor details, invoice number, items, prices, taxes, and expiry dates without hallucination.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-850 border border-slate-700/60">
              <div className="text-sm font-semibold text-white flex items-center gap-2">
                <span className="p-1 rounded bg-amber-500/20 text-amber-400">2</span>
                Dual-Catalog Fuzzy Matching
              </div>
              <p className="text-xs text-slate-400 mt-2">
                Items are matched against both your local inventory and global master databases, calculating confidence scores (HIGH, MED, LOW).
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-850 border border-slate-700/60">
              <div className="text-sm font-semibold text-white flex items-center gap-2">
                <span className="p-1 rounded bg-emerald-500/20 text-emerald-400">3</span>
                Human Verification & Atomic Commit
              </div>
              <p className="text-xs text-slate-400 mt-2">
                You review and edit extracted numbers before committing. On confirmation, an atomic database transaction updates inventory stock and batches.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: RECEIPT REVIEW SCREEN (RULE 36 & 37) */}
      {activeView === 'review' && activeImport && (
        <div className="space-y-6 animate-fadeIn">
          {/* Status banner */}
          <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <AlertCircle size={20} className="text-amber-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Verification Required Before Database Insertion</h3>
                <p className="text-xs text-amber-200/70">
                  Review extracted vendor info, product matches, quantities, and cost prices. Unverified AI data will not enter inventory until you confirm.
                </p>
              </div>
            </div>

            <button
              onClick={handleConfirmImport}
              disabled={confirming || items.length === 0}
              className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-sm transition shadow-lg shadow-emerald-600/25 flex items-center gap-2 whitespace-nowrap"
            >
              <CheckCircle2 size={18} />
              <span>{confirming ? 'Executing Atomic Transaction…' : 'Confirm & Import into Inventory'}</span>
            </button>
          </div>

          {/* Header Metadata (Editable) */}
          <div className="p-5 rounded-xl bg-slate-850 border border-slate-700/60 space-y-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Invoice & Supplier Metadata
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Supplier Name</label>
                <input
                  type="text"
                  value={supplierName}
                  onChange={(e) => setSupplierName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-sm focus:border-indigo-500 outline-none"
                  placeholder="Supplier Name"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Supplier GSTIN</label>
                <input
                  type="text"
                  value={supplierGstin}
                  onChange={(e) => setSupplierGstin(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-sm focus:border-indigo-500 outline-none font-mono"
                  placeholder="27AABCU9603R1ZM"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Invoice Number</label>
                <input
                  type="text"
                  value={invoiceNumber}
                  onChange={(e) => setInvoiceNumber(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-sm focus:border-indigo-500 outline-none font-mono"
                  placeholder="INV-10291"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Invoice Date</label>
                <input
                  type="date"
                  value={invoiceDate}
                  onChange={(e) => setInvoiceDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-sm focus:border-indigo-500 outline-none"
                />
              </div>
            </div>
          </div>

          {/* Line Items Table */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-850 overflow-hidden">
            <div className="p-4 bg-slate-800/80 border-b border-slate-700 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-white text-sm">Extracted Line Items ({items.length})</h3>
                <p className="text-xs text-slate-400">Click any value to modify before finalizing.</p>
              </div>
              <button
                onClick={addNewItem}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium transition"
              >
                <Plus size={14} />
                <span>Add Product</span>
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-900/60 text-xs uppercase text-slate-400 border-b border-slate-700/60">
                  <tr>
                    <th className="py-3 px-3">Product Name</th>
                    <th className="py-3 px-3">Catalog Match</th>
                    <th className="py-3 px-3">Qty</th>
                    <th className="py-3 px-3">Unit Cost (₹)</th>
                    <th className="py-3 px-3">MRP (₹)</th>
                    <th className="py-3 px-3">GST %</th>
                    <th className="py-3 px-3">Batch & Expiry</th>
                    <th className="py-3 px-3">Total (₹)</th>
                    <th className="py-3 px-3 text-right">Remove</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {items.map((item, idx) => {
                    const lineTot = (Number(item.quantity) || 0) * (Number(item.purchase_price) || 0)
                    return (
                      <tr key={idx} className="hover:bg-slate-800/30 transition">
                        {/* Name */}
                        <td className="py-2.5 px-3 min-w-[180px]">
                          <input
                            type="text"
                            value={item.raw_product_name}
                            onChange={(e) => updateItem(idx, 'raw_product_name', e.target.value)}
                            className="w-full px-2 py-1 rounded bg-slate-900/80 border border-slate-700 text-white text-xs"
                          />
                        </td>

                        {/* Match Status & Confidence */}
                        <td className="py-2.5 px-3 min-w-[160px]">
                          <div className="flex flex-col gap-1">
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold w-fit ${
                                item.confidence_level === 'HIGH'
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : item.confidence_level === 'MEDIUM'
                                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              }`}
                            >
                              {item.confidence_level === 'HIGH' ? '✓' : '⚠'} {item.confidence_score}% Match
                            </span>
                            <span className="text-[11px] text-slate-400 truncate max-w-[150px]">
                              {item.matched_product_name || (item.match_source === 'master' ? 'Master Product' : 'New Local Product')}
                            </span>
                          </div>
                        </td>

                        {/* Quantity */}
                        <td className="py-2.5 px-3 w-20">
                          <input
                            type="number"
                            min="1"
                            value={item.quantity}
                            onChange={(e) => updateItem(idx, 'quantity', Number(e.target.value))}
                            className="w-16 px-2 py-1 rounded bg-slate-900/80 border border-slate-700 text-white text-xs font-mono font-bold"
                          />
                        </td>

                        {/* Cost Price */}
                        <td className="py-2.5 px-3 w-24">
                          <input
                            type="number"
                            step="0.01"
                            value={item.purchase_price}
                            onChange={(e) => updateItem(idx, 'purchase_price', Number(e.target.value))}
                            className="w-20 px-2 py-1 rounded bg-slate-900/80 border border-slate-700 text-white text-xs font-mono"
                          />
                        </td>

                        {/* MRP */}
                        <td className="py-2.5 px-3 w-24">
                          <input
                            type="number"
                            step="0.01"
                            value={item.mrp || ''}
                            onChange={(e) => updateItem(idx, 'mrp', Number(e.target.value))}
                            className="w-20 px-2 py-1 rounded bg-slate-900/80 border border-slate-700 text-white text-xs font-mono"
                            placeholder="MRP"
                          />
                        </td>

                        {/* GST % */}
                        <td className="py-2.5 px-3 w-20">
                          <input
                            type="number"
                            value={item.gst_percentage}
                            onChange={(e) => updateItem(idx, 'gst_percentage', Number(e.target.value))}
                            className="w-16 px-2 py-1 rounded bg-slate-900/80 border border-slate-700 text-white text-xs font-mono"
                          />
                        </td>

                        {/* Batch & Expiry */}
                        <td className="py-2.5 px-3 min-w-[150px]">
                          <div className="space-y-1">
                            <input
                              type="text"
                              value={item.batch_number || ''}
                              onChange={(e) => updateItem(idx, 'batch_number', e.target.value)}
                              placeholder="Batch #"
                              className="w-full px-2 py-0.5 rounded bg-slate-900/80 border border-slate-700 text-white text-[11px] font-mono"
                            />
                            <input
                              type="date"
                              value={item.expiry_date || ''}
                              onChange={(e) => updateItem(idx, 'expiry_date', e.target.value)}
                              className="w-full px-2 py-0.5 rounded bg-slate-900/80 border border-slate-700 text-white text-[11px]"
                            />
                          </div>
                        </td>

                        {/* Total */}
                        <td className="py-2.5 px-3 font-mono font-semibold text-white whitespace-nowrap">
                          ₹{lineTot.toFixed(2)}
                        </td>

                        {/* Action */}
                        <td className="py-2.5 px-3 text-right">
                          <button
                            onClick={() => removeItem(idx)}
                            className="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition"
                            title="Remove line item"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Verification Footer Summary */}
            <div className="p-4 bg-slate-900/80 border-t border-slate-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="text-xs text-slate-400">
                <span>Items count: <b className="text-white">{items.length}</b></span>
                <span className="mx-2">•</span>
                <span>AI Confidence: <b className="text-emerald-400">{activeImport.ai_confidence}%</b></span>
              </div>

              <div className="flex items-center gap-6 text-sm">
                <div>
                  <span className="text-slate-400">Subtotal: </span>
                  <span className="font-mono text-white font-medium">₹{computedSubtotal.toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-slate-400">GST: </span>
                  <span className="font-mono text-white font-medium">₹{computedGst.toFixed(2)}</span>
                </div>
                <div className="text-base">
                  <span className="text-slate-400">Grand Total: </span>
                  <span className="font-mono font-bold text-emerald-400">₹{computedGrandTotal.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 3: RECEIPT INGESTION HISTORY */}
      {activeView === 'history' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Receipt Ingestion History</h2>
            <button
              onClick={fetchReceipts}
              className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:text-white"
            >
              <RefreshCw size={15} />
            </button>
          </div>

          {imports.length === 0 ? (
            <div className="p-12 text-center rounded-xl bg-slate-850 border border-slate-700/60 text-slate-400">
              <FileCheck2 size={36} className="mx-auto text-slate-500 mb-2 opacity-60" />
              <p className="font-medium text-white">No receipts processed yet.</p>
              <p className="text-sm mt-1">Upload a receipt or invoice to test automated processing.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-850">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">Invoice #</th>
                    <th className="py-3 px-4">Supplier</th>
                    <th className="py-3 px-4">Uploaded By</th>
                    <th className="py-3 px-4">Total Amount</th>
                    <th className="py-3 px-4">AI Score</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {imports.map((imp) => (
                    <tr key={imp.id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4 font-mono font-medium text-white">{imp.invoice_number || `REC-${imp.id}`}</td>
                      <td className="py-3 px-4 text-xs text-slate-300">{imp.supplier_name || 'Vendor'}</td>
                      <td className="py-3 px-4 text-xs text-slate-400">{imp.uploaded_by}</td>
                      <td className="py-3 px-4 font-mono font-semibold text-emerald-400">
                        ₹{(imp.total_amount || 0).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-xs">
                        <span className="px-2 py-0.5 rounded font-mono font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          {imp.ai_confidence}%
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                            imp.processing_status === 'imported'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : imp.processing_status === 'review_required'
                              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              : 'bg-slate-700 text-slate-300'
                          }`}
                        >
                          {imp.processing_status.replace('_', ' ').toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-400">
                        {imp.created_at ? new Date(imp.created_at).toLocaleDateString() : 'Recent'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => loadReceiptDetail(imp.id)}
                          className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium transition"
                        >
                          {imp.processing_status === 'imported' ? 'View Details' : 'Review'}
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
    </div>
  )
}
