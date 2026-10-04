import { FormEvent, useEffect, useState } from 'react'
import {
  Boxes,
  CheckCircle2,
  Download,
  Package,
  PackagePlus,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  X
} from 'lucide-react'
import { api } from '../lib/api'
import type { InventoryBatch, MasterCatalogItem, Product } from '../types'
import { StatusBadge } from '../components/StatusBadge'
import LoadingState from '../components/LoadingState'

type Category = {
  id: number
  name: string
  is_grocery?: boolean
  default_weight_unit?: 'kg' | 'g'
  default_weight_g?: number
  weight_increment_g?: number
  minimum_weight_g?: number
  maximum_weight_g?: number
}
type Supplier = { id: number; name: string }

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [query, setQuery] = useState('')
  const [showProductForm, setShowProductForm] = useState(false)
  const [showBatchModal, setShowBatchModal] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [productBatches, setProductBatches] = useState<InventoryBatch[]>([])
  const [loadingProducts, setLoadingProducts] = useState(true)
  const [loadingBatches, setLoadingBatches] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [weightBased, setWeightBased] = useState(false)
  const [weightUnit, setWeightUnit] = useState<'kg' | 'g'>('kg')

  // Master Catalog Exploration & Import state
  const [viewMode, setViewMode] = useState<'local' | 'master'>('local')
  const [masterQuery, setMasterQuery] = useState('')
  const [masterProducts, setMasterProducts] = useState<MasterCatalogItem[]>([])
  const [searchingMaster, setSearchingMaster] = useState(false)
  const [importingProduct, setImportingProduct] = useState<MasterCatalogItem | null>(null)
  const [importSellingPrice, setImportSellingPrice] = useState<number>(100)
  const [importPurchasePrice, setImportPurchasePrice] = useState<number>(75)
  const [importStock, setImportStock] = useState<number>(20)
  const [importReorderLevel, setImportReorderLevel] = useState<number>(10)
  const [importSupplierId, setImportSupplierId] = useState<number | undefined>(undefined)

  const selectedCategory = categories.find((c) => String(c.id) === categoryId) || categories[0]

  const load = async () => {
    setLoadingProducts(true)
    try {
      const response = await api<{ items: Product[] }>('/api/products?page_size=100')
      setProducts(response.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load products.')
    } finally {
      setLoadingProducts(false)
    }
  }

  useEffect(() => {
    load()
    api<Category[]>('/api/categories').then((rows) => {
      setCategories(rows)
      if (rows.length > 0) setCategoryId(String(rows[0].id))
    }).catch(() => {})
    api<Supplier[]>('/api/suppliers').then((sups) => {
      setSuppliers(sups)
      if (sups.length > 0) setImportSupplierId(sups[0].id)
    }).catch(() => {})
  }, [])

  async function openProductDetail(p: Product) {
    setSelectedProduct(p)
    setLoadingBatches(true)
    try {
      const full = await api<Product & { batches: InventoryBatch[] }>(`/api/products/${p.id}`)
      setSelectedProduct(full)
      setProductBatches(full.batches || [])
    } catch {
      setProductBatches([])
    } finally {
      setLoadingBatches(false)
    }
  }

  async function searchMasterCatalog(searchTerm: string) {
    if (!searchTerm.trim()) return
    setSearchingMaster(true)
    setError('')
    try {
      const res = await api<{ master_products: MasterCatalogItem[] }>(
        `/api/catalog/search?q=${encodeURIComponent(searchTerm.trim())}`
      )
      setMasterProducts(res.master_products || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not query master catalog')
    } finally {
      setSearchingMaster(false)
    }
  }

  async function executeImport(e: FormEvent) {
    e.preventDefault()
    if (!importingProduct) return
    setError('')
    try {
      await api('/api/catalog/import', {
        method: 'POST',
        body: JSON.stringify({
          master_product_id: importingProduct.master_id,
          selling_price: importSellingPrice,
          purchase_price: importPurchasePrice,
          initial_stock: importStock,
          reorder_level: importReorderLevel,
          supplier_id: importSupplierId
        })
      })
      setSuccess(`Imported "${importingProduct.product_name}" into your local inventory!`)
      setImportingProduct(null)
      setViewMode('local')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    }
  }

  async function createProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const form = new FormData(event.currentTarget)
    const body = {
      name: String(form.get('name')),
      category_id: Number(form.get('category')),
      supplier_id: Number(form.get('supplier')),
      price: Number(form.get('price')),
      minimum_stock: Number(form.get('minimum') ?? form.get('reorder')),
      maximum_stock: Number(form.get('maximum') ?? form.get('reorder')),
      reorder_point: Number(form.get('reorder')),
      safety_stock: Number(form.get('safety')),
      lead_time_days: Number(form.get('lead')),
      unit: weightBased ? 'kg' : 'pack',
      status: 'active',
      is_weight_based: weightBased,
      weight_unit: weightBased ? String(form.get('weight_unit')) : null,
      default_weight_g: weightBased
        ? Math.round(Number(form.get('default_weight')) * (String(form.get('weight_unit')) === 'kg' ? 1000 : 1))
        : null,
      weight_increment_g: weightBased
        ? Math.round(Number(form.get('weight_increment')) * (String(form.get('weight_unit')) === 'kg' ? 1000 : 1))
        : null,
      minimum_weight_g: weightBased
        ? Math.round(Number(form.get('minimum_weight')) * (String(form.get('weight_unit')) === 'kg' ? 1000 : 1))
        : null,
      maximum_weight_g: weightBased
        ? Math.round(Number(form.get('maximum_weight')) * (String(form.get('weight_unit')) === 'kg' ? 1000 : 1))
        : null,
      weight_stock_g: weightBased
        ? Math.round(Number(form.get('weight_stock')) * (String(form.get('weight_unit')) === 'kg' ? 1000 : 1))
        : null,
      current_stock: weightBased ? 0 : Number(form.get('stock'))
    }
    try {
      const created = await api<Product>('/api/products', { method: 'POST', body: JSON.stringify(body) })
      setShowProductForm(false)
      setSuccess(`Product created with SKU ${created.sku}.`)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create product')
    }
  }

  async function handleReceiveBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const form = new FormData(event.currentTarget)
    const productId = Number(form.get('product_id'))
    const body = {
      product_id: productId,
      lot_number: String(form.get('lot_number')),
      quantity: Number(form.get('quantity')),
      received_date: String(form.get('received_date') || new Date().toISOString().slice(0, 10)),
      expiry_date: form.get('expiry_date') ? String(form.get('expiry_date')) : null
    }
    try {
      await api('/api/inventory/batches', { method: 'POST', body: JSON.stringify(body) })
      setShowBatchModal(false)
      setSuccess(`Batch ${body.lot_number} received successfully. Stock updated.`)
      load()
      if (selectedProduct && selectedProduct.id === productId) {
        openProductDetail(selectedProduct)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not receive batch')
    }
  }

  async function handleAdjustStock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedProduct) return
    setError('')
    const form = new FormData(event.currentTarget)
    const delta = Number(form.get('delta'))
    const type = String(form.get('type'))
    const note = String(form.get('note') || '')
    try {
      if (selectedProduct.is_weight_based) {
        const factor = selectedProduct.weight_unit === 'kg' ? 1000 : 1
        const result = await api<{ weight_stock_g: number }>(`/api/inventory/${selectedProduct.id}/weight-adjust`, {
          method: 'POST',
          body: JSON.stringify({ weight_delta_g: Math.round(delta * factor), transaction_type: type, note })
        })
        setSelectedProduct({ ...selectedProduct, weight_stock_g: result.weight_stock_g })
        setSuccess(`Weight stock adjusted. New balance: ${(result.weight_stock_g / 1000).toFixed(3)} kg`)
        load()
        return
      }
      const res = await api<{ current_stock: number }>(`/api/inventory/${selectedProduct.id}/adjust`, {
        method: 'POST',
        body: JSON.stringify({ quantity_delta: delta, transaction_type: type, note })
      })
      setSelectedProduct({ ...selectedProduct, current_stock: res.current_stock })
      setSuccess(`Stock adjusted. New balance: ${res.current_stock}`)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Adjustment failed')
    }
  }

  const shown = products.filter((p) =>
    `${p.name} ${p.sku} ${p.category_name || ''}`.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">CATALOG & INVENTORY</p>
          <h1>Products & Inventory</h1>
          <p>Local store inventory, Master catalog synchronization, batch traceability, and stock balance.</p>
        </div>
        <div className="header-actions">
          <button className="secondary-button" onClick={() => setShowBatchModal(true)}>
            <PackagePlus size={17} />
            Receive Batch
          </button>
          <button
            className="secondary-button"
            onClick={() => {
              const next = viewMode === 'local' ? 'master' : 'local'
              setViewMode(next)
              if (next === 'master' && masterProducts.length === 0) {
                searchMasterCatalog('a')
              }
            }}
          >
            <Boxes size={17} />
            {viewMode === 'local' ? 'Search Master Catalog' : 'View Local Inventory'}
          </button>
          <button className="primary-button" onClick={() => setShowProductForm(!showProductForm)}>
            <Plus size={17} />
            Add Custom Product
          </button>
        </div>
      </header>

      {success && (
        <div className="insight-strip" style={{ marginBottom: 16 }}>
          <span>{success}</span>
          <button className="icon-button" onClick={() => setSuccess('')}>
            <X size={14} />
          </button>
        </div>
      )}

      {error && (
        <div className="insight-strip" style={{ marginBottom: 16, background: '#faebeb', color: '#8c2417', borderColor: '#f2c6c2' }}>
          <span>{error}</span>
          <button className="icon-button" onClick={() => setError('')}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* Add product form stays in the inventory page so the catalog remains visible. */}
      {showProductForm && (
        <section className="panel" style={{ padding: 20, marginBottom: 18 }} aria-labelledby="add-product-heading">
          <div className="section-heading" style={{ marginBottom: 16 }}>
            <div>
              <p className="eyebrow">LOCAL INVENTORY</p>
              <h2 id="add-product-heading">Add Custom Local Product</h2>
              <p className="subtle-text">The SKU is generated automatically per business. Incoming receipts add to both current stock and the reorder threshold.</p>
            </div>
            <button className="secondary-button" type="button" onClick={() => setShowProductForm(false)}>Cancel</button>
          </div>
          <form onSubmit={createProduct} style={{ display: 'grid', gap: 12 }}>
            <div className="form-grid">
              <label>Product Name<input name="name" required placeholder="Product Name" /></label>
              <label>SKU<input value="Generated automatically on save" readOnly aria-label="SKU generated automatically" /></label>
              <label>Category<select name="category" value={categoryId} onChange={(e) => setCategoryId(e.target.value)} required>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
              <label>Supplier<select name="supplier" required>{suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
              <label>Selling Price (₹)<input name="price" type="number" step="0.01" min="0.01" required /></label>
              <label>Initial Stock<input name="stock" type="number" min="0" required defaultValue="10" /></label>
              <label>Reorder Threshold<input name="reorder" type="number" min="0" required defaultValue="10" /></label>
              <label>Minimum Stock<input name="minimum" type="number" min="0" required defaultValue="10" /></label>
              <label>Maximum Stock<input name="maximum" type="number" min="0" required defaultValue="100" /></label>
              <label>Safety Stock<input name="safety" type="number" min="0" required defaultValue="5" /></label>
              <label>Supplier Lead Time (days)<input name="lead" type="number" min="0" required defaultValue="3" /></label>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
              <button type="button" className="secondary-button" onClick={() => setShowProductForm(false)}>Cancel</button>
              <button type="submit" className="primary-button">Save Product</button>
            </div>
          </form>
        </section>
      )}


      {/* Import to Local Store Modal */}
      {importingProduct && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: 540 }}>
            <div className="modal-header">
              <div>
                <p className="eyebrow">MASTER CATALOG IMPORT</p>
                <h2>Import to Local Store</h2>
              </div>
              <button className="icon-button" onClick={() => setImportingProduct(null)}>
                <X size={17} />
              </button>
            </div>
            <form onSubmit={executeImport} style={{ display: 'grid', gap: 12 }}>
              <div style={{ background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}>
                <strong style={{ fontSize: 15, color: '#1e293b' }}>{importingProduct.product_name}</strong>
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                  SKU: {importingProduct.sku} • Category: {importingProduct.category || 'General'}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <label>
                  Selling Price (₹)
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={importSellingPrice}
                    onChange={(e) => setImportSellingPrice(Number(e.target.value))}
                  />
                </label>
                <label>
                  Purchase / Cost Price (₹)
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={importPurchasePrice}
                    onChange={(e) => setImportPurchasePrice(Number(e.target.value))}
                  />
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <label>
                  Initial Stock Quantity
                  <input
                    type="number"
                    min="0"
                    required
                    value={importStock}
                    onChange={(e) => setImportStock(Number(e.target.value))}
                  />
                </label>
                <label>
                  Reorder Level Threshold
                  <input
                    type="number"
                    min="1"
                    required
                    value={importReorderLevel}
                    onChange={(e) => setImportReorderLevel(Number(e.target.value))}
                  />
                </label>
              </div>

              <label>
                Assigned Supplier
                <select
                  value={importSupplierId || ''}
                  onChange={(e) => setImportSupplierId(Number(e.target.value))}
                >
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
                <button type="button" className="secondary-button" onClick={() => setImportingProduct(null)}>
                  Cancel
                </button>
                <button type="submit" className="primary-button">
                  Confirm Import to Store
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MASTER CATALOG EXPLORER VIEW */}
      {viewMode === 'master' ? (
        <section className="panel table-panel">
          <div className="table-toolbar">
            <div className="search" style={{ minWidth: 320 }}>
              <Search size={16} />
              <input
                value={masterQuery}
                onChange={(e) => setMasterQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && searchMasterCatalog(masterQuery)}
                placeholder="Search global master catalog products..."
              />
            </div>
            <button
              className="primary-button"
              onClick={() => searchMasterCatalog(masterQuery || 'a')}
              disabled={searchingMaster}
              style={{ minHeight: 34, padding: '0 14px' }}
            >
              {searchingMaster ? 'Searching Master DB…' : 'Search Master'}
            </button>
            <span style={{ fontSize: 13, color: '#64748b' }}>
              {masterProducts.length} items available in global master catalog
            </span>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Master Product</th>
                  <th>SKU / Barcode</th>
                  <th>Brand</th>
                  <th>Category</th>
                  <th>Store Status</th>
                  <th style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {masterProducts.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: 30, color: '#64748b' }}>
                      {searchingMaster ? 'Querying master PostgreSQL database…' : 'Search products above to browse global master catalog.'}
                    </td>
                  </tr>
                ) : (
                  masterProducts.map((mp) => (
                    <tr key={mp.master_id}>
                      <td>
                        <strong>{mp.product_name}</strong>
                        {mp.description && <small style={{ display: 'block', color: '#64748b' }}>{mp.description}</small>}
                      </td>
                      <td>
                        <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{mp.sku}</span>
                      </td>
                      <td>{mp.brand || 'Generic'}</td>
                      <td>{mp.category || 'General'}</td>
                      <td>
                        {mp.already_imported ? (
                          <span className="badge" style={{ background: '#e0f2fe', color: '#0369a1' }}>
                            ✓ In Store
                          </span>
                        ) : (
                          <span className="badge" style={{ background: '#f1f5f9', color: '#475569' }}>
                            Available to Import
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {mp.already_imported ? (
                          <span style={{ fontSize: 12, color: '#94a3b8' }}>Imported</span>
                        ) : (
                          <button
                            className="primary-button"
                            onClick={() => {
                              setImportingProduct(mp)
                              setImportSellingPrice(120)
                              setImportPurchasePrice(90)
                              setImportStock(25)
                              setImportReorderLevel(10)
                            }}
                            style={{ minHeight: 28, padding: '0 10px', fontSize: 12 }}
                          >
                            <Download size={13} style={{ marginRight: 4 }} />
                            Import to Store
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        /* LOCAL STORE INVENTORY TABLE */
        <section className="panel table-panel">
          <div className="table-toolbar">
            <div className="search">
              <Search size={16} />
              <input
                aria-label="Search local inventory"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search local store products by name, SKU or category..."
              />
            </div>
            <span>{shown.length} local products (click row to view details & batches)</span>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Category</th>
                  <th>Supplier</th>
                  <th>Current Stock</th>
                  <th>Reorder Threshold</th>
                  <th>Unit Price</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {loadingProducts ? <tr><td colSpan={7}><LoadingState label="Loading products…" /></td></tr> : shown.map((p) => (
                  <tr
                    key={p.id}
                    className="clickable-row"
                    onClick={() => openProductDetail(p)}
                    title="Click to view details, active batches and shelf life"
                  >
                    <td>
                      <strong>{p.name}</strong>
                      <small>{p.sku}</small>
                    </td>
                    <td>{p.category_name || p.category || 'General'}</td>
                    <td>{p.supplier_name || 'Primary Supplier'}</td>
                    <td className={p.is_weight_based ? '' : p.reorder_point > 0 && p.current_stock * 5 < p.reorder_point ? 'danger-text' : ''}>
                      {p.is_weight_based
                        ? `${((p.weight_stock_g || 0) / 1000).toFixed(3).replace(/\.?0+$/, '')} kg`
                        : `${p.current_stock}/${p.reorder_point} ${p.unit}`}
                    </td>
                    <td>{p.reorder_point}</td>
                    <td>₹{p.price}{p.is_weight_based ? ' / kg' : ''}</td>
                    <td>
                      <StatusBadge value={!p.is_weight_based && p.reorder_point > 0 && p.current_stock * 5 < p.reorder_point ? 'LOW' : p.status} />
                    </td>
                  </tr>
                ))}
                {!loadingProducts && !shown.length && <tr><td colSpan={7} className="empty-row">No products match your search.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Selected Product Detail Panel */}
      {selectedProduct && (
        <div className="product-detail-overlay" onClick={() => setSelectedProduct(null)}>
          <div className="product-detail-modal" onClick={(e) => e.stopPropagation()}>
            <div className="detail-header">
              <div>
                <p className="eyebrow">PRODUCT DETAILS</p>
                <h2>{selectedProduct.name}</h2>
                <small className="detail-sku">SKU: {selectedProduct.sku}</small>
              </div>
              <button className="icon-button" onClick={() => setSelectedProduct(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="detail-metrics">
              <div className="detail-card">
                <span className="card-label">Current Stock</span>
                <span className={`card-value ${!selectedProduct.is_weight_based && selectedProduct.reorder_point > 0 && selectedProduct.current_stock * 5 < selectedProduct.reorder_point ? 'danger-text' : ''}`}>
                  {selectedProduct.current_stock}/{selectedProduct.reorder_point}
                </span>
                <small>{selectedProduct.unit}</small>
              </div>
              <div className="detail-card">
                <span className="card-label">Reorder Point</span>
                <span className="card-value">{selectedProduct.reorder_point}</span>
                <small>threshold</small>
              </div>
              <div className="detail-card">
                <span className="card-label">Price</span>
                <span className="card-value">₹{selectedProduct.price}</span>
                <small>selling</small>
              </div>
            </div>

            <div className="panel" style={{ padding: 16 }}>
              <h3 style={{ margin: '0 0 10px', fontSize: 14 }}>Batch Traceability</h3>
              {loadingBatches ? (
                <p>Loading batches…</p>
              ) : productBatches.length === 0 ? (
                <p className="subtle-text">No active batches recorded.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Lot Number</th>
                        <th>Qty</th>
                        <th>Received</th>
                        <th>Expiry</th>
                      </tr>
                    </thead>
                    <tbody>
                      {productBatches.map((b) => (
                        <tr key={b.id}>
                          <td><strong>{b.lot_number}</strong></td>
                          <td>{b.quantity}</td>
                          <td>{b.received_date}</td>
                          <td>{b.expiry_date || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="panel" style={{ padding: 16 }}>
              <h3 style={{ margin: '0 0 10px', fontSize: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                <SlidersHorizontal size={15} /> Quick Stock Adjustment
              </h3>
              <form onSubmit={handleAdjustStock}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <label style={{ fontSize: 12 }}>
                    Adjustment Delta (+ / -)
                    <input name="delta" type="number" step="1" required placeholder="+10 or -5" />
                  </label>
                  <label style={{ fontSize: 12 }}>
                    Reason
                    <select name="type">
                      <option value="adjustment">Count Adjustment</option>
                      <option value="receipt">Stock Receipt</option>
                      <option value="waste">Damaged / Waste</option>
                      <option value="transfer">Transfer</option>
                    </select>
                  </label>
                </div>
                <button type="submit" className="primary-button" style={{ marginTop: 10, width: '100%' }}>
                  Apply Adjustment
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Receive Batch Modal */}
      {showBatchModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="modal-header">
              <h2>Receive Inventory Batch</h2>
              <button className="icon-button" onClick={() => setShowBatchModal(false)}>
                <X size={17} />
              </button>
            </div>
            <form onSubmit={handleReceiveBatch}>
              <label>
                Product
                <select name="product_id" required>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Lot / Batch Number
                <input name="lot_number" required placeholder="LOT-2026-001" />
              </label>
              <label>
                Quantity
                <input name="quantity" type="number" min="1" required />
              </label>
              <label>
                Expiry Date
                <input name="expiry_date" type="date" />
              </label>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
                <button type="button" className="secondary-button" onClick={() => setShowBatchModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary-button">
                  Record Batch
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </>
  )
}
