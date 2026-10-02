export type User = {
  id: number
  email: string
  full_name: string
  role: 'admin' | 'business_owner' | 'associate'
  is_active: boolean
  business_id?: number | null
  business_name?: string | null
  business_type?: 'medical' | 'grocery' | 'restaurant' | 'food' | 'stationery' | 'dairy' | 'clothing' | 'others' | string | null
  permissions?: string[]
}

export type InventoryBatch = {
  id: number
  product_id: number
  product_name?: string
  lot_number: string
  quantity: number
  received_date?: string
  expiry_date?: string | null
  days_remaining?: number | null
  status?: string
}

export type Product = {
  id: number
  sku: string
  name: string
  product_name?: string
  category_id?: number
  category_name?: string
  category?: string
  subcategory?: string
  category_is_grocery?: boolean
  supplier_id?: number
  supplier_name?: string
  price: number
  selling_price?: number
  purchase_price?: number
  mrp?: number | null
  current_stock: number
  minimum_stock?: number
  maximum_stock?: number
  reorder_point: number
  reorder_level?: number
  safety_stock?: number
  lead_time_days?: number
  expiry_date?: string | null
  unit: string
  status: string
  generic_name?: string | null
  dosage_form?: string | null
  strength?: string | null
  manufacturer?: string | null
  prescription_required?: boolean
  is_weight_based?: boolean
  weight_unit?: 'kg' | 'g' | null
  default_weight_g?: number | null
  weight_increment_g?: number | null
  minimum_weight_g?: number | null
  maximum_weight_g?: number | null
  weight_stock_g?: number | null
  batches?: InventoryBatch[]
}

export type Dashboard = {
  last_updated: string
  kpis: Record<string, number>
  sales_trend: { date: string; revenue: number; units: number }[]
  category_sales: { name: string; value: number }[]
}

export type MasterCatalogItem = {
  master_id: string
  sku: string
  barcode: string | null
  product_name: string
  brand: string | null
  category: string | null
  subcategory: string | null
  description: string | null
  already_imported?: boolean
  is_local?: boolean
}

export type ReceiptItem = {
  id?: number
  raw_product_name: string
  matched_product_id?: number | null
  matched_product_name?: string | null
  master_product_id?: string | null
  match_source?: 'local' | 'master' | 'new_unmatched'
  quantity: number
  unit: string
  barcode?: string | null
  serial_number?: string | null
  purchase_price: number
  mrp?: number | null
  gst_percentage: number
  batch_number?: string | null
  expiry_date?: string | null
  confidence_score: number
  confidence_level: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'
  review_status: string
}

export type ReceiptImport = {
  id: number
  file_name: string
  uploaded_by: string
  supplier_name?: string | null
  invoice_number?: string | null
  invoice_date?: string | null
  processing_status: 'uploaded' | 'processing' | 'extracted' | 'review_required' | 'partially_reviewed' | 'confirmed' | 'imported' | 'failed'
  subtotal: number
  gst_amount: number
  total_amount: number
  ai_confidence: number
  created_at: string
  confirmed_at?: string | null
  confirmed_by?: string | null
  items?: ReceiptItem[]
}

export type StoreCapability = {
  name: string
  business_type: string
  units: string[]
  default_unit: string
  allow_decimals: boolean
  expiry_warning_days: number
  features: {
    weight?: boolean
    volume?: boolean
    expiry?: boolean
    batch?: boolean
    serial_number?: boolean
    size?: boolean
    color?: boolean
    variants?: boolean
    pack_size?: boolean
    custom_attributes?: boolean
  }
}

export type ReorderItem = {
  id?: number
  product_id: number
  sku: string
  barcode?: string | null
  product_name: string
  brand?: string | null
  category?: string | null
  current_stock: number
  reorder_level: number
  target_stock?: number
  purchase_price?: number
  previous_price?: number
  selling_price?: number
  supplier_id?: number | null
  supplier_name?: string | null
  last_order_quantity?: number
  last_order_date?: string | null
  order_count?: number
  average_quantity?: number
  average_order_quantity?: number
  suggested_quantity: number
  selected_quantity?: number
  received_quantity?: number
  remaining_quantity?: number
  status?: string
  reason?: string
  source?: string
  notes?: string | null
  unit?: string
  pack_size?: string | null
  size?: string | null
  color?: string | null
  style?: string | null
  variant_name?: string | null
  expired_quantity?: number
  expiring_quantity?: number
  earliest_expiry?: string | null
  latest_expiry?: string | null
  expired_batches_count?: number
}

export type PendingReorderItem = {
  id: number
  product_id: number
  product_name: string
  sku: string
  barcode?: string | null
  category?: string | null
  brand?: string | null
  supplier_id?: number
  supplier_name: string
  current_stock: number
  reorder_level: number
  target_stock?: number
  suggested_quantity: number
  selected_quantity: number
  received_quantity: number
  remaining_quantity: number
  last_order_date?: string | null
  last_order_quantity?: number
  status: string
  purchase_price?: number
  estimated_cost: number
  source?: string
  reason?: string
  notes?: string | null
  unit?: string
  pack_size?: string | null
  size?: string | null
  color?: string | null
  style?: string | null
  variant_name?: string | null
}

export type ReceivingHistoryItem = {
  id: number
  product_id: number
  product_name: string
  sku: string
  barcode?: string | null
  previous_stock: number
  received_quantity: number
  new_stock: number
  unit: string
  lot_number?: string | null
  serial_number?: string | null
  expiry_date?: string | null
  performed_by: string
  transaction_id?: string | null
  note?: string | null
  received_at?: string | null
  source?: string
  size?: string | null
  color?: string | null
}

export type ReorderOverview = {
  business_type?: string
  store_capability?: StoreCapability
  summary?: {
    total_reorders: number
    low_stock_count: number
    expired_count: number
    expiring_soon_count: number
    manual_reorders_count: number
    partially_received_count: number
  }
  low_stock: ReorderItem[]
  expired_stock: ReorderItem[]
  expiring_soon_stock?: ReorderItem[]
  previously_ordered: ReorderItem[]
  frequently_ordered: ReorderItem[]
  recently_ordered: ReorderItem[]
  suggested_reorders: ReorderItem[]
  pending_reorders: PendingReorderItem[]
  completed_reorders: {
    id: number
    po_number: string
    supplier_id?: number
    supplier_name: string
    status: string
    total_amount: number
    created_at: string
    expected_delivery?: string | null
    item_count: number
  }[]
  receiving_history?: ReceivingHistoryItem[]
}

export type WholesalerCandidate = {
  product_id: number
  product_name: string
  sku?: string | null
  barcode?: string | null
  size?: string | null
  color?: string | null
  score: number
}

export type WholesalerItem = {
  id?: number
  raw_product_name: string
  matched_product_id?: number | null
  matched_product_name?: string | null
  quantity: number
  unit?: string
  barcode?: string | null
  serial_number?: string | null
  batch_number?: string | null
  expiry_date?: string | null
  purchase_price?: number
  mrp?: number | null
  size?: string | null
  color?: string | null
  style?: string | null
  variant_name?: string | null
  confidence_score?: number
  confidence_level?: string
  status?: 'matched' | 'needs_review' | 'not_found' | 'invalid' | 'duplicate'
  error_message?: string | null
  candidates?: WholesalerCandidate[]
}

export type WholesalerDocResponse = {
  status: string
  filename: string
  format: string
  file_hash?: string
  duplicate_delivery_warning?: string | null
  supplier_name: string
  invoice_number: string
  invoice_date: string
  subtotal: number
  total_amount: number
  items_count: number
  summary?: {
    total_rows: number
    matched: number
    needs_review: number
    not_found: number
    invalid: number
    duplicates: number
    ready_to_add: number
  }
  items: WholesalerItem[]
}

export type AssociateUser = {
  id: number
  full_name: string
  email: string
  is_active: boolean
  role: string
  business_id: number
  created_at?: string | null
  permissions: string[]
}
