export type User = {
  id: number
  email: string
  full_name: string
  role: 'admin' | 'business_owner' | 'associate'
  is_active: boolean
  business_id?: number | null
  business_name?: string | null
  business_type?: 'medical' | 'grocery' | 'restaurant' | 'stationery' | 'dairy' | null
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

export type ReorderItem = {
  id?: number
  product_id: number
  sku: string
  product_name: string
  brand?: string | null
  category?: string | null
  current_stock: number
  reorder_level: number
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
  status?: string
  reason?: string
}

export type ReorderOverview = {
  low_stock: ReorderItem[]
  previously_ordered: ReorderItem[]
  frequently_ordered: ReorderItem[]
  recently_ordered: ReorderItem[]
  suggested_reorders: ReorderItem[]
  pending_reorders: {
    id: number
    product_id: number
    product_name: string
    sku: string
    supplier_id?: number
    supplier_name: string
    current_stock: number
    reorder_level: number
    suggested_quantity: number
    selected_quantity: number
    last_order_date?: string | null
    last_order_quantity?: number
    status: string
    estimated_cost: number
  }[]
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
