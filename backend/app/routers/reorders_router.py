"""
Dedicated Universal Reorder Management & Stock Ingestion Router
Supports:
- Universal multi-store adaptability (Grocery, Medical, Stationery, Food, Dairy, Clothing, Others)
- Expired & Expiring Soon stock detection with configurable warning periods (no expiry forced on clothing/stationery)
- Automatic replenishment detection (current_stock <= reorder_level)
- Strict deduplication: Low Stock + Expired merged into one multi-reason reorder row
- Variant-aware reorders for clothing and apparel (Size, Color, Style)
- Product-specific decimal and integer quantity controls (kg, g, L, ml, piece, pack, box, set, pair)
- Multi-format CSV export with BOM, escaped quotes/commas, string-preserved barcodes (leading zeros intact), and store-tailored columns
- Physical stock receiving into local inventory (single & bulk receiving, separate receive quantity, partial/full delivery tracking)
- Wholesaler delivery file ingestion (.csv, .xlsx, .xls, .json, .txt, .pdf, .png, .jpg)
- File hash deduplication (detects duplicate delivery uploads before stock update)
- Product matching hierarchy: 1. Barcode > 2. SKU > 3. Serial > 4. Variant > 5. Exact Name > 6. Fuzzy Match
- Ambiguous match review ('needs_review' with candidate matches) and unknown product handling ('not_found')
- Server-authoritative atomic database transactions with SELECT FOR UPDATE concurrency protection
- Full inventory transaction and stock receiving audit history
"""

import io
import os
import re
import csv
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database_manager import get_master_session
from ..dependencies import get_current_user, get_local_db, get_master_db, require_permission
from ..rate_limit import limiter
from ..models import User
from ..services.receipt_service import (
    check_duplicate_delivery,
    clean_str_code,
    compute_file_hash,
    extract_text_from_pdf,
    match_items_with_catalogs,
    parse_receipt_text_or_vision,
    validate_receipt_file
)
from ..services.store_config import (
    get_store_capability,
    normalize_business_type,
    validate_store_item_quantity
)

router = APIRouter(prefix="/api/reorders", tags=["Reorder List"])


class ReorderItemInput(BaseModel):
    product_id: Optional[int] = None
    product_name: Optional[str] = Field(None, min_length=2, max_length=255)
    product_unit: Optional[str] = Field(None, min_length=1, max_length=50)
    product_category: Optional[str] = Field(None, max_length=150)
    product_size: Optional[str] = Field(None, max_length=50)
    product_color: Optional[str] = Field(None, max_length=50)
    product_style: Optional[str] = Field(None, max_length=100)
    supplier_name: Optional[str] = Field(None, max_length=255)
    purchase_price: Optional[float] = Field(None, ge=0)
    supplier_id: Optional[int] = None
    suggested_quantity: float = Field(default=10.0, gt=0)
    selected_quantity: float = Field(default=10.0, gt=0)
    source: str = "manual"
    reason: Optional[str] = "Manual addition"
    notes: Optional[str] = None
    mode: Optional[str] = "prompt"  # 'prompt' | 'increase' | 'replace'
    force_update: Optional[bool] = False


class ReorderItemUpdate(BaseModel):
    selected_quantity: Optional[float] = Field(None, gt=0)
    supplier_id: Optional[int] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


class CreatePOFromReorderInput(BaseModel):
    supplier_id: int
    reorder_item_ids: List[int]
    expected_delivery: Optional[str] = None


class ReorderPreviousPurchaseInput(BaseModel):
    purchase_id: int
    adjust_quantities: Optional[Dict[int, float]] = None


class ReceiveItemInput(BaseModel):
    reorder_id: Optional[int] = None
    product_id: int
    received_quantity: float = Field(gt=0, default=1.0)
    batch_number: Optional[str] = None
    serial_number: Optional[str] = None
    expiry_date: Optional[str] = None
    purchase_price: Optional[float] = None
    mrp: Optional[float] = None
    barcode: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    note: Optional[str] = None


class ReceiveStockInput(BaseModel):
    items: List[ReceiveItemInput]
    general_note: Optional[str] = None


class WholesalerConfirmItem(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    quantity: float = Field(gt=0, default=1.0)
    unit: Optional[str] = "unit"
    barcode: Optional[str] = None
    serial_number: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None
    purchase_price: Optional[float] = 0.0
    mrp: Optional[float] = None
    size: Optional[str] = None
    color: Optional[str] = None
    style: Optional[str] = None
    variant_name: Optional[str] = None


class WholesalerConfirmRequest(BaseModel):
    supplier_name: Optional[str] = "Wholesaler"
    invoice_number: Optional[str] = None
    file_hash: Optional[str] = None
    items: List[WholesalerConfirmItem]
    note: Optional[str] = None


def sync_reorder_stock(local_db: Session, business_type: str = "grocery") -> int:
    """
    Scans local business inventory according to store capability:
    1. Condition A: Low Stock (current stock is below 20% of reorder level)
    2. Condition B: Expired Stock (expiry_date <= CURRENT_DATE and quantity > 0)
    3. Condition C: Expiring Soon Stock (expiry_date <= CURRENT_DATE + warning_days)
       * Expiry checks only apply if store capability allows expiry (skipped for clothing/stationery).
    4. NO DUPLICATE REORDER ROWS:
       Merges Low Stock + Expired into a single consolidated reorder row with dual reasons.
    5. Preserves variant identity for clothing/apparel.
    """
    cap = get_store_capability(business_type)
    supports_expiry = cap["features"].get("expiry", False)
    warning_days = cap.get("expiry_warning_days", 7)

    expired_map: Dict[int, Dict[str, Any]] = {}
    expiring_soon_map: Dict[int, Dict[str, Any]] = {}

    if supports_expiry:
        # Fetch products with expired batches
        expired_rows = local_db.execute(text("""
            SELECT ib.product_id,
                   COALESCE(SUM(ib.quantity), 0) as expired_qty,
                   MIN(ib.expiry_date) as earliest_expiry
            FROM inventory_batches ib
            JOIN products p ON ib.product_id = p.id
            WHERE ib.expiry_date <= CURRENT_DATE AND ib.quantity > 0 AND p.status = 'active'
            GROUP BY ib.product_id
        """)).fetchall()
        expired_map = {r[0]: {"expired_qty": float(r[1]), "earliest_expiry": r[2]} for r in expired_rows}

        # Fetch products expiring soon within warning period
        if warning_days > 0:
            cutoff_date = date.today() + timedelta(days=warning_days)
            expiring_rows = local_db.execute(text("""
                SELECT ib.product_id,
                       COALESCE(SUM(ib.quantity), 0) as expiring_qty,
                       MIN(ib.expiry_date) as earliest_expiry
                FROM inventory_batches ib
                JOIN products p ON ib.product_id = p.id
                WHERE ib.expiry_date > CURRENT_DATE AND ib.expiry_date <= :cutoff
                  AND ib.quantity > 0 AND p.status = 'active'
                GROUP BY ib.product_id
            """), {"cutoff": cutoff_date}).fetchall()
            expiring_soon_map = {r[0]: {"expiring_qty": float(r[1]), "earliest_expiry": r[2]} for r in expiring_rows}

    # Fetch products with low stock
    low_rows = local_db.execute(text("""
        SELECT p.id, p.current_stock, p.reorder_level, p.supplier_id, p.purchase_price, p.unit, p.target_stock
        FROM products p
        WHERE p.reorder_level > 0 AND p.current_stock * 5 < p.reorder_level AND p.status = 'active'
    """)).fetchall()
    low_map = {
        r[0]: {
            "current_stock": float(r[1] or 0),
            "reorder_level": float(r[2] or 0),
            "supplier_id": r[3],
            "purchase_price": float(r[4] or 0),
            "unit": r[5] or "unit",
            "target_stock": float(r[6] or 0),
        } for r in low_rows
    }

    candidate_ids = set(expired_map.keys()) | set(expiring_soon_map.keys()) | set(low_map.keys())
    if not candidate_ids:
        return 0

    synced_count = 0
    for pid in candidate_ids:
        prod = local_db.execute(text("""
            SELECT id, current_stock, reorder_level, supplier_id, purchase_price, product_name, unit, target_stock, size, color
            FROM products WHERE id = :id
        """), {"id": pid}).fetchone()
        if not prod:
            continue

        cstock = float(prod[1] or 0)
        rlevel = float(prod[2] or 0)
        sup_id = prod[3]
        cost = float(prod[4] or 0)
        pname = prod[5]
        punit = prod[6] or "unit"
        ptarget = float(prod[7] or 0)
        psize = prod[8]
        pcolor = prod[9]

        # Get last purchase order history
        last_order = local_db.execute(text("""
            SELECT pi.quantity, pur.purchase_date
            FROM purchase_items pi
            JOIN purchases pur ON pi.purchase_id = pur.id
            WHERE pi.product_id = :id
            ORDER BY pur.purchase_date DESC LIMIT 1
        """), {"id": pid}).fetchone()
        last_qty = float(last_order[0]) if last_order else 20.0
        last_date = last_order[1] if last_order else None

        is_exp = pid in expired_map
        is_expiring = pid in expiring_soon_map
        is_low = cstock <= rlevel

        # Calculate target or suggested quantity
        base_target = ptarget if ptarget > 0 else (rlevel * 2)

        # Merge conditions to avoid duplicate reorder rows
        if is_exp and is_low:
            exp_info = expired_map[pid]
            expired_qty = exp_info["expired_qty"]
            source = "expired_and_low"
            reason = f"Low stock ({cstock}/{rlevel} {punit}), Expired ({expired_qty} {punit})"
            suggested_qty = max((base_target - cstock) + expired_qty, last_qty)
        elif is_exp:
            exp_info = expired_map[pid]
            expired_qty = exp_info["expired_qty"]
            earliest_date = exp_info["earliest_expiry"].isoformat() if exp_info["earliest_expiry"] else "past"
            source = "expired_stock"
            reason = f"Expired stock: {expired_qty} {punit} expired on {earliest_date}"
            suggested_qty = max(expired_qty, last_qty or 10.0)
        elif is_low and is_expiring:
            exp_info = expiring_soon_map[pid]
            expiring_qty = exp_info["expiring_qty"]
            source = "expiring_and_low"
            reason = f"Low stock ({cstock}/{rlevel} {punit}), Expiring Soon ({expiring_qty} {punit})"
            suggested_qty = max(base_target - cstock + expiring_qty, last_qty)
        elif is_expiring:
            exp_info = expiring_soon_map[pid]
            expiring_qty = exp_info["expiring_qty"]
            source = "expiring_soon"
            reason = f"Expiring soon: {expiring_qty} {punit} within warning window"
            suggested_qty = max(expiring_qty, last_qty or 10.0)
        else:
            source = "low_stock"
            reason = f"Low stock: {cstock} {punit} remaining (Reorder level: {rlevel} {punit})"
            suggested_qty = max(base_target - cstock, last_qty or 20.0)

        # Enforce valid quantity steps / decimal constraints
        suggested_qty = validate_store_item_quantity(business_type, suggested_qty)

        # Upsert into reorder_list without creating duplicate rows
        local_db.execute(text("""
            INSERT INTO reorder_list (
                product_id, supplier_id, current_stock, reorder_level, target_stock,
                suggested_quantity, selected_quantity, received_quantity, last_order_date,
                last_order_quantity, status, source, reason, created_at, updated_at
            ) VALUES (
                :pid, :sid, :cstock, :rlevel, :ptarget,
                :sug, :sel, 0, :ldate,
                :lqty, 'pending', :src, :reason, NOW(), NOW()
            )
            ON CONFLICT (product_id) DO UPDATE SET
                current_stock = EXCLUDED.current_stock,
                reorder_level = EXCLUDED.reorder_level,
                target_stock = EXCLUDED.target_stock,
                suggested_quantity = EXCLUDED.suggested_quantity,
                selected_quantity = CASE
                    WHEN reorder_list.status = 'received' THEN EXCLUDED.suggested_quantity
                    WHEN reorder_list.selected_quantity <= 0 THEN EXCLUDED.suggested_quantity
                    ELSE reorder_list.selected_quantity
                END,
                supplier_id = COALESCE(reorder_list.supplier_id, EXCLUDED.supplier_id),
                last_order_date = EXCLUDED.last_order_date,
                last_order_quantity = EXCLUDED.last_order_quantity,
                source = EXCLUDED.source,
                reason = EXCLUDED.reason,
                status = CASE WHEN reorder_list.status = 'received' THEN 'pending' ELSE reorder_list.status END,
                updated_at = NOW()
        """), {
            "pid": pid,
            "sid": sup_id,
            "cstock": cstock,
            "rlevel": rlevel,
            "ptarget": ptarget,
            "sug": suggested_qty,
            "sel": suggested_qty,
            "ldate": last_date,
            "lqty": last_qty,
            "src": source,
            "reason": reason
        })
        synced_count += 1

    local_db.commit()
    return synced_count


@router.post("/auto-populate")
@limiter.limit("10/minute")
def trigger_auto_populate(
    request: Request,
    user: User = Depends(require_permission("reorder.create")),
    local_db: Session = Depends(get_local_db)
):
    """Explicitly triggers auto-sync for low stock, expired, and expiring soon products."""
    b_type = getattr(user, "business_type_val", "grocery") or "grocery"
    count = sync_reorder_stock(local_db, b_type)
    return {
        "message": f"Reorder list auto-synced successfully. {count} product(s) analyzed and updated.",
        "synced_count": count,
        "business_type": b_type
    }


@router.get("/catalog-search")
def search_local_catalog(
    q: str = Query("", min_length=1),
    user: User = Depends(require_permission("reorder.view")),
    local_db: Session = Depends(get_local_db)
):
    """Search products in store catalog to add them manually to reorder list."""
    term = f"%{q.strip()}%"
    rows = local_db.execute(text("""
        SELECT p.id, p.sku, p.barcode, p.product_name, p.category, p.current_stock,
               p.reorder_level, p.target_stock, p.purchase_price, p.supplier_id, s.name as supplier_name,
               p.unit, p.pack_size, p.size, p.color, p.style, p.variant_name
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.status = 'active'
          AND (p.product_name ILIKE :term OR p.sku ILIKE :term OR p.barcode ILIKE :term
               OR p.size ILIKE :term OR p.color ILIKE :term OR p.variant_name ILIKE :term)
        ORDER BY p.product_name ASC
        LIMIT 30
    """), {"term": term}).fetchall()

    return [{
        "product_id": r[0],
        "sku": r[1],
        "barcode": r[2],
        "product_name": r[3],
        "category": r[4],
        "current_stock": float(r[5] or 0),
        "reorder_level": float(r[6] or 0),
        "target_stock": float(r[7] or 0),
        "purchase_price": float(r[8] or 0),
        "supplier_id": r[9],
        "supplier_name": r[10] or "Standard Supplier",
        "unit": r[11] or "unit",
        "pack_size": r[12],
        "size": r[13],
        "color": r[14],
        "style": r[15],
        "variant_name": r[16],
    } for r in rows]


@router.get("/overview")
def get_reorder_overview(
    user: User = Depends(require_permission("reorder.view")),
    local_db: Session = Depends(get_local_db)
):
    """
    Returns comprehensive reorder overview adapted to the active store/business type:
    - store_capability: feature flags, units, quantity precision
    - summary: total reorders, low stock, expired, expiring soon, manual, partially received
    - low_stock
    - expired_stock
    - expiring_soon_stock
    - previously_ordered
    - frequently_ordered
    - recently_ordered
    - suggested_reorders
    - pending_reorders (with remaining quantities, batch/serial/variant fields)
    - completed_reorders
    - receiving_history
    """
    b_type = getattr(user, "business_type_val", "grocery") or "grocery"
    cap = get_store_capability(b_type)

    # 1. Low Stock Products (read-only, auto-sync is triggered via POST /auto-populate)
    low_stock_rows = local_db.execute(text("""
        SELECT p.id, p.sku, p.barcode, p.product_name, p.brand, p.category, p.current_stock,
               p.reorder_level, p.target_stock, p.purchase_price, p.selling_price, p.supplier_id,
               s.name as supplier_name, p.unit, p.pack_size, p.size, p.color, p.style, p.variant_name,
               (SELECT pi.quantity FROM purchase_items pi WHERE pi.product_id = p.id ORDER BY pi.id DESC LIMIT 1) as last_qty,
               (SELECT pur.purchase_date FROM purchases pur JOIN purchase_items pi ON pur.id = pi.purchase_id WHERE pi.product_id = p.id ORDER BY pur.id DESC LIMIT 1) as last_date
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.reorder_level > 0 AND p.current_stock * 5 < p.reorder_level AND p.status = 'active'
        ORDER BY (p.current_stock - p.reorder_level) ASC
        LIMIT 100
    """)).fetchall()

    low_stock = [{
        "product_id": r[0],
        "sku": r[1],
        "barcode": r[2],
        "product_name": r[3],
        "brand": r[4],
        "category": r[5],
        "current_stock": float(r[6] or 0),
        "reorder_level": float(r[7] or 0),
        "target_stock": float(r[8] or 0),
        "purchase_price": float(r[9] or 0),
        "selling_price": float(r[10] or 0),
        "supplier_id": r[11],
        "supplier_name": r[12] or "Default Supplier",
        "unit": r[13] or "unit",
        "pack_size": r[14],
        "size": r[15],
        "color": r[16],
        "style": r[17],
        "variant_name": r[18],
        "last_order_quantity": float(r[19]) if r[19] is not None else 20.0,
        "last_order_date": r[20].isoformat() if r[20] else None,
        "suggested_quantity": max(float(r[7] or 10) * 2 - float(r[6] or 0), float(r[19] or 20.0)),
    } for r in low_stock_rows]

    # 3. Expired Stock Products (only if store supports expiry)
    expired_stock = []
    expiring_soon_stock = []
    if cap["features"].get("expiry", False):
        expired_rows = local_db.execute(text("""
            SELECT p.id, p.sku, p.barcode, p.product_name, p.brand, p.category, p.current_stock,
                   p.reorder_level, p.purchase_price, p.selling_price, p.supplier_id,
                   s.name as supplier_name, p.unit, p.pack_size,
                   SUM(ib.quantity) as expired_quantity,
                   MIN(ib.expiry_date) as earliest_expiry,
                   MAX(ib.expiry_date) as latest_expiry,
                   COUNT(ib.id) as expired_batches_count,
                   (SELECT pi.quantity FROM purchase_items pi WHERE pi.product_id = p.id ORDER BY pi.id DESC LIMIT 1) as last_qty,
                   (SELECT pur.purchase_date FROM purchases pur JOIN purchase_items pi ON pur.id = pi.purchase_id WHERE pi.product_id = p.id ORDER BY pur.id DESC LIMIT 1) as last_date
            FROM products p
            JOIN inventory_batches ib ON p.id = ib.product_id
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            WHERE ib.expiry_date <= CURRENT_DATE AND ib.quantity > 0 AND p.status = 'active'
            GROUP BY p.id, p.sku, p.barcode, p.product_name, p.brand, p.category, p.current_stock,
                     p.reorder_level, p.purchase_price, p.selling_price, p.supplier_id, s.name, p.unit, p.pack_size
            ORDER BY earliest_expiry ASC
            LIMIT 100
        """)).fetchall()

        expired_stock = [{
            "product_id": r[0],
            "sku": r[1],
            "barcode": r[2],
            "product_name": r[3],
            "brand": r[4],
            "category": r[5],
            "current_stock": float(r[6] or 0),
            "reorder_level": float(r[7] or 0),
            "purchase_price": float(r[8] or 0),
            "selling_price": float(r[9] or 0),
            "supplier_id": r[10],
            "supplier_name": r[11] or "Default Supplier",
            "unit": r[12] or "unit",
            "pack_size": r[13],
            "expired_quantity": float(r[14] or 0),
            "earliest_expiry": r[15].isoformat() if r[15] else None,
            "latest_expiry": r[16].isoformat() if r[16] else None,
            "expired_batches_count": r[17],
            "last_order_quantity": float(r[18]) if r[18] is not None else 20.0,
            "last_order_date": r[19].isoformat() if r[19] else None,
            "suggested_quantity": max(float(r[14] or 0), float(r[18] or 10.0)),
        } for r in expired_rows]

        # Expiring Soon
        warning_days = cap.get("expiry_warning_days", 7)
        if warning_days > 0:
            cutoff = date.today() + timedelta(days=warning_days)
            soon_rows = local_db.execute(text("""
                SELECT p.id, p.sku, p.barcode, p.product_name, p.brand, p.category, p.current_stock,
                       p.reorder_level, p.purchase_price, p.supplier_id, s.name as supplier_name,
                       p.unit, p.pack_size, SUM(ib.quantity) as expiring_qty, MIN(ib.expiry_date) as earliest_exp
                FROM products p
                JOIN inventory_batches ib ON p.id = ib.product_id
                LEFT JOIN suppliers s ON p.supplier_id = s.id
                WHERE ib.expiry_date > CURRENT_DATE AND ib.expiry_date <= :cutoff
                  AND ib.quantity > 0 AND p.status = 'active'
                GROUP BY p.id, p.sku, p.barcode, p.product_name, p.brand, p.category, p.current_stock,
                         p.reorder_level, p.purchase_price, p.supplier_id, s.name, p.unit, p.pack_size
                ORDER BY earliest_exp ASC
                LIMIT 100
            """), {"cutoff": cutoff}).fetchall()

            expiring_soon_stock = [{
                "product_id": r[0],
                "sku": r[1],
                "barcode": r[2],
                "product_name": r[3],
                "brand": r[4],
                "category": r[5],
                "current_stock": float(r[6] or 0),
                "reorder_level": float(r[7] or 0),
                "purchase_price": float(r[8] or 0),
                "supplier_id": r[9],
                "supplier_name": r[10] or "Default Supplier",
                "unit": r[11] or "unit",
                "pack_size": r[12],
                "expiring_quantity": float(r[13] or 0),
                "earliest_expiry": r[14].isoformat() if r[14] else None,
                "suggested_quantity": float(r[13] or 10.0),
            } for r in soon_rows]

    # 4. Previously Ordered Items
    prev_ordered_rows = local_db.execute(text("""
        SELECT p.id, p.sku, p.barcode, p.product_name, p.current_stock, p.reorder_level,
               s.id as supplier_id, s.name as supplier_name,
               pi.unit_price, pi.quantity as last_qty, pur.purchase_date as last_date,
               pur.id as purchase_id, p.unit, p.size, p.color
        FROM purchase_items pi
        JOIN purchases pur ON pi.purchase_id = pur.id
        JOIN products p ON pi.product_id = p.id
        LEFT JOIN suppliers s ON pur.supplier_id = s.id
        ORDER BY pur.purchase_date DESC, pi.id DESC
        LIMIT 50
    """)).fetchall()

    previously_ordered = [{
        "product_id": r[0],
        "sku": r[1],
        "barcode": r[2],
        "product_name": r[3],
        "current_stock": float(r[4] or 0),
        "reorder_level": float(r[5] or 0),
        "supplier_id": r[6],
        "supplier_name": r[7] or "Verified Supplier",
        "previous_price": float(r[8] or 0),
        "last_order_quantity": float(r[9] or 0),
        "last_order_date": r[10].isoformat() if r[10] else None,
        "purchase_id": r[11],
        "unit": r[12] or "unit",
        "size": r[13],
        "color": r[14],
        "suggested_quantity": float(r[9] or 10),
    } for r in prev_ordered_rows]

    # 5. Frequently Ordered Items
    freq_rows = local_db.execute(text("""
        SELECT p.id, p.sku, p.barcode, p.product_name, COUNT(pi.id) as order_count,
               AVG(pi.quantity) as avg_qty, p.current_stock, p.reorder_level,
               p.supplier_id, s.name as supplier_name, p.unit, p.size, p.color
        FROM purchase_items pi
        JOIN products p ON pi.product_id = p.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        GROUP BY p.id, p.sku, p.barcode, p.product_name, p.current_stock, p.reorder_level, p.supplier_id, s.name, p.unit, p.size, p.color
        ORDER BY order_count DESC
        LIMIT 20
    """)).fetchall()

    frequently_ordered = [{
        "product_id": r[0],
        "sku": r[1],
        "barcode": r[2],
        "product_name": r[3],
        "order_count": r[4],
        "average_quantity": round(float(r[5] or 0), 1),
        "current_stock": float(r[6] or 0),
        "reorder_level": float(r[7] or 0),
        "supplier_id": r[8],
        "supplier_name": r[9] or "Preferred Vendor",
        "unit": r[10] or "unit",
        "size": r[11],
        "color": r[12],
        "suggested_quantity": round(float(r[5] or 20)),
    } for r in freq_rows]

    # 6. Recently Ordered Items (last 30 days)
    cutoff_date = date.today() - timedelta(days=30)
    rec_rows = local_db.execute(text("""
        SELECT DISTINCT ON (p.id) p.id, p.sku, p.barcode, p.product_name, pur.purchase_date,
               pi.quantity, pi.unit_price, s.name as supplier_name, pur.id as purchase_id, p.unit, p.size, p.color
        FROM purchases pur
        JOIN purchase_items pi ON pur.id = pi.purchase_id
        JOIN products p ON pi.product_id = p.id
        LEFT JOIN suppliers s ON pur.supplier_id = s.id
        WHERE pur.purchase_date >= :cutoff
        ORDER BY p.id, pur.purchase_date DESC
        LIMIT 25
    """), {"cutoff": cutoff_date}).fetchall()

    recently_ordered = [{
        "product_id": r[0],
        "sku": r[1],
        "barcode": r[2],
        "product_name": r[3],
        "order_date": r[4].isoformat() if r[4] else None,
        "quantity": float(r[5] or 0),
        "unit_price": float(r[6] or 0),
        "supplier_name": r[7] or "Vendor",
        "purchase_id": r[8],
        "unit": r[9] or "unit",
        "size": r[10],
        "color": r[11],
    } for r in rec_rows]

    # 7. Suggested Reorders
    suggested = []
    for item in low_stock:
        suggested.append({
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "barcode": item.get("barcode"),
            "sku": item.get("sku"),
            "size": item.get("size"),
            "color": item.get("color"),
            "unit": item.get("unit"),
            "current_stock": item["current_stock"],
            "reorder_level": item["reorder_level"],
            "last_ordered_quantity": item["last_order_quantity"],
            "last_order_date": item["last_order_date"],
            "supplier_id": item["supplier_id"],
            "supplier_name": item["supplier_name"],
            "suggested_quantity": item["suggested_quantity"],
            "reason": "Stock below reorder threshold",
        })

    # 8. Pending & Partially Received Items in Reorder List
    pending_rows = local_db.execute(text("""
        SELECT rl.id, rl.product_id, p.product_name, p.sku, p.barcode, p.category, p.brand,
               rl.supplier_id, s.name as supplier_name, rl.current_stock, rl.reorder_level, rl.target_stock,
               rl.suggested_quantity, rl.selected_quantity, COALESCE(rl.received_quantity, 0),
               rl.last_order_date, rl.last_order_quantity, rl.status, p.purchase_price,
               rl.source, rl.reason, rl.notes, p.unit, p.pack_size, p.size, p.color, p.style, p.variant_name
        FROM reorder_list rl
        JOIN products p ON rl.product_id = p.id
        LEFT JOIN suppliers s ON rl.supplier_id = s.id
        WHERE rl.status IN ('pending', 'partially_received', 'ordered')
        ORDER BY rl.created_at DESC
    """)).fetchall()

    pending_reorders = []
    partially_received_count = 0
    manual_reorders_count = 0

    for r in pending_rows:
        sel_qty = float(r[13] or 0)
        recv_qty = float(r[14] or 0)
        rem_qty = max(sel_qty - recv_qty, 0.0)
        cost_price = float(r[18] or 0)
        status_val = r[17] or "pending"
        source_val = r[19] or "low_stock"

        if status_val == "partially_received":
            partially_received_count += 1
        if source_val == "manual":
            manual_reorders_count += 1

        pending_reorders.append({
            "id": r[0],
            "product_id": r[1],
            "product_name": r[2],
            "sku": r[3],
            "barcode": r[4],
            "category": r[5],
            "brand": r[6],
            "supplier_id": r[7],
            "supplier_name": r[8] or "Vendor",
            "current_stock": float(r[9] or 0),
            "reorder_level": float(r[10] or 0),
            "target_stock": float(r[11] or 0),
            "suggested_quantity": float(r[12] or 0),
            "selected_quantity": sel_qty,
            "received_quantity": recv_qty,
            "remaining_quantity": rem_qty,
            "last_order_date": r[15].isoformat() if r[15] else None,
            "last_order_quantity": float(r[16] or 0),
            "status": status_val,
            "purchase_price": cost_price,
            "estimated_cost": round(cost_price * rem_qty, 2),
            "source": source_val,
            "reason": r[20] or "Replenishment required",
            "notes": r[21],
            "unit": r[22] or "unit",
            "pack_size": r[23],
            "size": r[24],
            "color": r[25],
            "style": r[26],
            "variant_name": r[27],
        })

    # 9. Completed Reorders
    po_rows = local_db.execute(text("""
        SELECT po.id, po.po_number, po.supplier_id, s.name as supplier_name,
               po.status, po.total_amount, po.created_at, po.expected_delivery,
               COUNT(poi.id) as item_count
        FROM purchase_orders po
        LEFT JOIN suppliers s ON po.supplier_id = s.id
        LEFT JOIN purchase_order_items poi ON po.id = poi.purchase_order_id
        GROUP BY po.id, po.po_number, po.supplier_id, s.name, po.status, po.total_amount, po.created_at, po.expected_delivery
        ORDER BY po.created_at DESC
        LIMIT 20
    """)).fetchall()

    completed_reorders = [{
        "id": r[0],
        "po_number": r[1],
        "supplier_id": r[2],
        "supplier_name": r[3] or "Supplier",
        "status": r[4],
        "total_amount": float(r[5] or 0),
        "created_at": r[6].isoformat() if r[6] else None,
        "expected_delivery": r[7].isoformat() if r[7] else None,
        "item_count": r[8],
    } for r in po_rows]

    # 10. Receiving History from inventory transactions
    recv_history_rows = local_db.execute(text("""
        SELECT it.id, it.product_id, p.product_name, p.sku, p.barcode,
               it.previous_stock, it.quantity, it.new_stock, p.unit,
               ib.lot_number, ib.serial_number, ib.expiry_date,
               it.performed_by, it.reference_id, it.note, it.timestamp
        FROM inventory_transactions it
        JOIN products p ON it.product_id = p.id
        LEFT JOIN inventory_batches ib ON it.batch_id = ib.id
        WHERE it.transaction_type IN ('REORDER_RECEIVED', 'Purchase')
        ORDER BY it.timestamp DESC
        LIMIT 40
    """)).fetchall()

    receiving_history = [{
        "id": r[0],
        "product_id": r[1],
        "product_name": r[2],
        "sku": r[3],
        "barcode": r[4],
        "previous_stock": float(r[5] or 0),
        "received_quantity": float(r[6] or 0),
        "new_stock": float(r[7] or 0),
        "unit": r[8] or "unit",
        "lot_number": r[9],
        "serial_number": r[10],
        "expiry_date": r[11].isoformat() if r[11] else None,
        "performed_by": r[12],
        "reference_id": r[13],
        "note": r[14],
        "received_at": r[15].isoformat() if r[15] else None,
    } for r in recv_history_rows]

    return {
        "business_type": b_type,
        "store_capability": cap,
        "summary": {
            "total_reorders": len(pending_reorders),
            "low_stock_count": len(low_stock),
            "expired_count": len(expired_stock),
            "expiring_soon_count": len(expiring_soon_stock),
            "manual_reorders_count": manual_reorders_count,
            "partially_received_count": partially_received_count,
        },
        "low_stock": low_stock,
        "expired_stock": expired_stock,
        "expiring_soon_stock": expiring_soon_stock,
        "previously_ordered": previously_ordered,
        "frequently_ordered": frequently_ordered,
        "recently_ordered": recently_ordered,
        "suggested_reorders": suggested,
        "pending_reorders": pending_reorders,
        "completed_reorders": completed_reorders,
        "receiving_history": receiving_history,
    }


@router.get("/export-csv")
def export_reorder_csv(
    ids: Optional[str] = Query(None, description="Comma-separated reorder item IDs. Defaults to all pending/partially received."),
    user: User = Depends(require_permission("reorder.view")),
    local_db: Session = Depends(get_local_db)
):
    """
    Exports the reorder stock list into an Excel/Spreadsheet-safe UTF-8 CSV with BOM.
    Ensures:
    - String preservation of barcodes and serial numbers (leading zeros never truncated, no scientific notation)
    - Store-tailored columns (omits irrelevant columns per business type)
    - Escaped commas and quotes
    - Decimal integrity for weight/volume units
    """
    b_type = getattr(user, "business_type_val", "grocery") or "grocery"
    cap = get_store_capability(b_type)

    where_clause = "rl.status IN ('pending', 'partially_received', 'ordered')"
    params: Dict[str, Any] = {}

    if ids:
        try:
            id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
            if id_list:
                where_clause += " AND rl.id = ANY(:ids)"
                params["ids"] = id_list
        except ValueError:
            pass

    sql = f"""
        SELECT p.product_name, p.id, p.sku, COALESCE(p.barcode, ''), COALESCE(p.unit, 'unit'),
               rl.current_stock, rl.reorder_level, rl.selected_quantity,
               COALESCE(rl.received_quantity, 0) as received_qty,
               GREATEST(rl.selected_quantity - COALESCE(rl.received_quantity, 0), 0) as remaining_qty,
               p.purchase_price,
               ROUND(GREATEST(rl.selected_quantity - COALESCE(rl.received_quantity, 0), 0) * p.purchase_price, 2) as estimated_cost,
               COALESCE(rl.reason, 'Stock Reorder'), COALESCE(s.name, 'Default Supplier'),
               COALESCE(rl.status, 'pending'), COALESCE(rl.notes, ''),
               p.size, p.color, p.style, p.variant_name, p.pack_size, p.brand,
               (SELECT ib.lot_number FROM inventory_batches ib WHERE ib.product_id = p.id AND ib.quantity > 0 ORDER BY ib.id DESC LIMIT 1) as latest_batch,
               (SELECT TO_CHAR(ib.expiry_date, 'YYYY-MM-DD') FROM inventory_batches ib WHERE ib.product_id = p.id AND ib.quantity > 0 ORDER BY ib.expiry_date ASC LIMIT 1) as earliest_exp
        FROM reorder_list rl
        JOIN products p ON rl.product_id = p.id
        LEFT JOIN suppliers s ON rl.supplier_id = s.id
        WHERE {where_clause}
        ORDER BY p.product_name ASC
    """
    rows = local_db.execute(text(sql), params).fetchall()

    output = io.StringIO()
    # Write UTF-8 BOM so Microsoft Excel interprets characters correctly without mangling
    output.write("\ufeff")
    writer = csv.writer(output, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

    # Dynamic columns based on business type
    is_clothing = cap["features"].get("variants", False) or b_type == "clothing"
    has_expiry = cap["features"].get("expiry", False)
    has_batch = cap["features"].get("batch", False)

    header = [
        "Product Name",
        "Product ID",
        "SKU",
        "Barcode",
        "Requested Quantity",
        "Received Quantity",
        "Remaining Quantity",
        "Unit",
        "Current Stock",
        "Reorder Level",
        "Unit Price (INR)",
        "Estimated Cost (INR)",
        "Supplier",
        "Status",
        "Reason",
        "Notes"
    ]

    if is_clothing:
        header.extend(["Size", "Color", "Style", "Variant Name"])
    if has_batch:
        header.append("Batch Number")
    if has_expiry:
        header.append("Expiry Date")
    if cap["features"].get("pack_size"):
        header.append("Pack Size")

    writer.writerow(header)

    for r in rows:
        pname = r[0]
        pid = r[1]
        sku = str(r[2])
        # Format barcode as string literal so Excel preserves leading zeros and avoids 1.23E+11
        raw_barcode = str(r[3]).strip()
        formatted_barcode = f'="{raw_barcode}"' if raw_barcode else ""
        unit = r[4]
        cstock = float(r[5] or 0)
        rlevel = float(r[6] or 0)
        req_qty = float(r[7] or 0)
        recv_qty = float(r[8] or 0)
        rem_qty = float(r[9] or 0)
        price = float(r[10] or 0)
        est_cost = float(r[11] or 0)
        supplier = r[13]
        status_str = r[14]
        reason_str = r[12]
        notes_str = r[15]

        row_data = [
            pname,
            pid,
            sku,
            formatted_barcode,
            req_qty,
            recv_qty,
            rem_qty,
            unit,
            cstock,
            rlevel,
            price,
            est_cost,
            supplier,
            status_str,
            reason_str,
            notes_str
        ]

        if is_clothing:
            row_data.extend([r[16] or "", r[17] or "", r[18] or "", r[19] or ""])
        if has_batch:
            row_data.append(r[22] or "")
        if has_expiry:
            row_data.append(r[23] or "")
        if cap["features"].get("pack_size"):
            row_data.append(r[20] or "")

        writer.writerow(row_data)

    csv_data = output.getvalue()
    filename = f"reorder-stock-{date.today().isoformat()}.csv"

    return StreamingResponse(
        iter([csv_data.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.post("/item")
@limiter.limit("20/minute")
def add_to_reorder(
    request: Request,
    body: ReorderItemInput,
    user: User = Depends(require_permission("reorder.create")),
    local_db: Session = Depends(get_local_db)
):
    """
    Add a product manually to the pending reorder list.
    Includes duplicate protection (Section 51):
    Alerts store manager if product is already in the active reorder list,
    with options to Increase Quantity or Edit Existing.
    """
    b_type = getattr(user, "business_type_val", "grocery") or "grocery"
    valid_qty = validate_store_item_quantity(b_type, body.selected_quantity)

    if body.product_id is None:
        if not body.product_name or not body.product_name.strip():
            raise HTTPException(422, "Choose a catalog product or enter a new product name.")
        local_db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"), {
            # Each tenant has its own local database, so the lock only needs to
            # serialize SKU allocation within this database.
            "lock_key": "local-product-sku-sequence"
        })
        existing_skus = local_db.execute(text("SELECT sku FROM products WHERE sku ~* '^SKU-[0-9]+$'")).fetchall()
        serials = [int(match.group(1)) for (sku,) in existing_skus if sku and (match := re.fullmatch(r"SKU-(\d+)", sku, re.IGNORECASE))]
        generated_sku = f"SKU-{max(serials, default=0) + 1:04d}"
        supplier_id = None
        if body.supplier_name and body.supplier_name.strip():
            name = body.supplier_name.strip()
            supplier_row = local_db.execute(text("SELECT id FROM suppliers WHERE lower(name) = lower(:name)"), {"name": name}).fetchone()
            if supplier_row:
                supplier_id = supplier_row[0]
            else:
                supplier_id = local_db.execute(text("INSERT INTO suppliers (name) VALUES (:name) RETURNING id"), {"name": name}).scalar()
        product_id = local_db.execute(text("""
            INSERT INTO products (
                sku, product_name, unit, current_stock, reorder_level, minimum_stock,
                maximum_stock, selling_price, purchase_price, supplier_id, category,
                size, color, style, variant_name, status
            ) VALUES (
                :sku, :name, :unit, 0, 0, 0, 500, 0, :purchase_price, :supplier_id,
                :category, :size, :color, :style, :variant_name, 'active'
            ) RETURNING id
        """), {
            "sku": generated_sku,
            "name": body.product_name.strip(),
            "unit": body.product_unit or "unit",
            "purchase_price": body.purchase_price or 0,
            "supplier_id": supplier_id,
            "category": body.product_category,
            "size": body.product_size,
            "color": body.product_color,
            "style": body.product_style,
            "variant_name": " ".join(value for value in (body.product_color, body.product_size) if value) or None,
        }).scalar()
        body.product_id = int(product_id)

    prod = local_db.execute(
        text("""
            SELECT id, current_stock, reorder_level, supplier_id, purchase_price, product_name, unit, size, color
            FROM products WHERE id = :id
        """),
        {"id": body.product_id}
    ).fetchone()
    if not prod:
        raise HTTPException(404, "Product not found in local catalog.")

    # Check for existing active reorder item
    existing = local_db.execute(text("""
        SELECT id, selected_quantity, received_quantity, status, reason
        FROM reorder_list
        WHERE product_id = :pid AND status IN ('pending', 'partially_received', 'ordered')
    """), {"pid": body.product_id}).fetchone()

    if existing and not body.force_update and body.mode == "prompt":
        return {
            "duplicate": True,
            "reorder_id": existing[0],
            "existing_reorder_id": existing[0],
            "current_requested_quantity": float(existing[1] or 0),
            "already_received_quantity": float(existing[2] or 0),
            "status": existing[3],
            "message": f'"{prod[5]}" is already in the active reorder list with requested quantity {float(existing[1] or 0)}. Choose to increase quantity or edit existing.'
        }

    final_qty = valid_qty
    if existing and body.mode == "increase":
        final_qty = float(existing[1] or 0) + valid_qty

    sup_id = body.supplier_id or prod[3]

    res = local_db.execute(text("""
        INSERT INTO reorder_list (
            product_id, supplier_id, current_stock, reorder_level,
            suggested_quantity, selected_quantity, received_quantity, status,
            source, reason, notes, created_at, updated_at
        ) VALUES (
            :pid, :sid, :cstock, :rlevel,
            :sug, :sel, 0, 'pending',
            :src, :reason, :notes, NOW(), NOW()
        )
        ON CONFLICT (product_id) DO UPDATE SET
            selected_quantity = :final_qty,
            received_quantity = CASE
                WHEN reorder_list.status = 'received' OR :mode = 'replace' THEN 0
                ELSE reorder_list.received_quantity
            END,
            suggested_quantity = CASE WHEN reorder_list.suggested_quantity <= 0 THEN :sug ELSE reorder_list.suggested_quantity END,
            supplier_id = COALESCE(reorder_list.supplier_id, EXCLUDED.supplier_id),
            reason = EXCLUDED.reason,
            notes = COALESCE(EXCLUDED.notes, reorder_list.notes),
            source = 'manual',
            status = 'pending',
            updated_at = NOW()
        RETURNING id
    """), {
        "pid": body.product_id,
        "sid": sup_id,
        "cstock": float(prod[1] or 0),
        "rlevel": float(prod[2] or 0),
        "sug": body.suggested_quantity,
        "sel": valid_qty,
        "final_qty": final_qty,
        "mode": body.mode or "prompt",
        "src": body.source or "manual",
        "reason": body.reason or "Manual addition by store manager",
        "notes": body.notes
    })
    local_db.commit()
    reorder_id = res.fetchone()[0]

    return {
        "message": f'"{prod[5]}" added to reorder list (Qty: {final_qty} {prod[6] or "units"}).',
        "reorder_id": reorder_id,
        "quantity": final_qty
    }


@router.put("/item/{reorder_id}")
def update_reorder_item(
    reorder_id: int,
    body: ReorderItemUpdate,
    user: User = Depends(require_permission("reorder.update")),
    local_db: Session = Depends(get_local_db)
):
    """Edit requested quantity, supplier, reason, or notes for a reorder item."""
    fields = []
    params: Dict[str, Any] = {"id": reorder_id}

    if body.selected_quantity is not None:
        if body.selected_quantity < 0:
            raise HTTPException(400, "Quantity cannot be negative.")
        fields.append("selected_quantity = :qty")
        params["qty"] = body.selected_quantity
    if body.supplier_id is not None:
        fields.append("supplier_id = :sid")
        params["sid"] = body.supplier_id
    if body.status is not None:
        fields.append("status = :status")
        params["status"] = body.status
    if body.reason is not None:
        fields.append("reason = :reason")
        params["reason"] = body.reason
    if body.notes is not None:
        fields.append("notes = :notes")
        params["notes"] = body.notes

    if not fields:
        return {"message": "No changes requested"}

    fields.append("updated_at = NOW()")
    sql = f"UPDATE reorder_list SET {', '.join(fields)} WHERE id = :id"
    local_db.execute(text(sql), params)
    local_db.commit()

    return {"message": "Reorder item updated successfully."}


@router.delete("/item/{reorder_id}")
def remove_reorder_item(
    reorder_id: int,
    user: User = Depends(require_permission("reorder.update")),
    local_db: Session = Depends(get_local_db)
):
    """Remove item from pending reorder list without deleting the product itself."""
    local_db.execute(text("DELETE FROM reorder_list WHERE id = :id"), {"id": reorder_id})
    local_db.commit()
    return {"message": "Item removed from pending reorder list."}


@router.post("/receive")
@limiter.limit("20/minute")
def receive_reorder_stock_into_inventory(
    request: Request,
    body: ReceiveStockInput,
    user: User = Depends(require_permission("reorder.update")),
    local_db: Session = Depends(get_local_db)
):
    """
    Physical Stock Receiving into Local Stock:
    - Supports receiving single item or bulk items (Select All).
    - Requires manager to enter actual received quantity (never assumes requested == received).
    - Supports full receipt and partial delivery (updates remaining quantity and sets status to 'partially_received').
    - Concurrency-safe: locks product row FOR UPDATE.
    - Server-authoritative transaction:
      1. Updates products.current_stock
      2. Creates inventory_batches (lot, serial, expiry, cost)
      3. Records inventory_transactions (type: 'REORDER_RECEIVED')
      4. Updates reorder_list item (marks received or partially_received)
    """
    if not body.items:
        raise HTTPException(400, "No items provided for stock receiving.")

    b_type = getattr(user, "business_type_val", "grocery") or "grocery"
    received_summary = []
    total_qty_received = 0.0

    try:
        for idx, item in enumerate(body.items):
            pid = item.product_id
            recv_qty = float(item.received_quantity)
            if recv_qty <= 0:
                continue

            # 1. Fetch current product record with FOR UPDATE row lock
            prod = local_db.execute(
                text("""
                    SELECT id, product_name, current_stock, purchase_price, barcode, unit, size, color
                    FROM products WHERE id = :id FOR UPDATE
                """),
                {"id": pid}
            ).fetchone()
            if not prod:
                continue

            prod_id, prod_name, curr_stock, curr_cost, curr_barcode, unit, psize, pcolor = prod
            prev_stock = float(curr_stock or 0)
            new_stock = prev_stock + recv_qty
            total_qty_received += recv_qty

            cost_price = float(item.purchase_price) if item.purchase_price is not None else float(curr_cost or 0)
            barcode_val = item.barcode or curr_barcode
            lot_no = item.batch_number or item.serial_number or f"LOT-RECV-{datetime.utcnow().strftime('%Y%m%d%H%M')}-{idx+1}"
            serial_no = clean_str_code(item.serial_number)

            # 2. Update Product Stock and Price
            local_db.execute(text("""
                UPDATE products
                SET current_stock = :new_stock,
                    reorder_level = reorder_level + :received_quantity,
                    purchase_price = CASE WHEN :cost > 0 THEN :cost ELSE purchase_price END,
                    mrp = COALESCE(:mrp, mrp),
                    barcode = COALESCE(:bc, barcode),
                    updated_at = NOW()
                WHERE id = :id
            """), {
                "new_stock": new_stock,
                "received_quantity": recv_qty,
                "cost": cost_price,
                "mrp": item.mrp,
                "bc": barcode_val,
                "id": prod_id
            })

            # 3. Create Inventory Batch
            exp_date_val = None
            if item.expiry_date:
                try:
                    exp_date_val = datetime.strptime(item.expiry_date[:10], "%Y-%m-%d").date()
                except Exception:
                    exp_date_val = None

            batch_res = local_db.execute(text("""
                INSERT INTO inventory_batches (
                    product_id, lot_number, serial_number, quantity, cost_price,
                    manufacturing_date, expiry_date, status, created_at
                ) VALUES (
                    :pid, :lot, :sn, :qty, :cost,
                    CURRENT_DATE, :exp, 'active', NOW()
                ) RETURNING id
            """), {
                "pid": prod_id,
                "lot": lot_no,
                "sn": serial_no,
                "qty": recv_qty,
                "cost": cost_price,
                "exp": exp_date_val
            })
            batch_id = batch_res.fetchone()[0]

            # 4. Record Inventory Transaction
            ref_code = f"RECV-{datetime.utcnow().strftime('%Y%m%d%H%M')}-{idx+1}"
            note_str = item.note or body.general_note or f"Stock received into local inventory | Lot: {lot_no} | S/N: {serial_no or '-'}"
            local_db.execute(text("""
                INSERT INTO inventory_transactions (
                    product_id, batch_id, transaction_type, quantity,
                    previous_stock, new_stock, reference_id, performed_by, note, timestamp
                ) VALUES (
                    :pid, :bid, 'REORDER_RECEIVED', :qty,
                    :prev, :new, :ref, :user, :note, NOW()
                )
            """), {
                "pid": prod_id,
                "bid": batch_id,
                "qty": recv_qty,
                "prev": prev_stock,
                "new": new_stock,
                "ref": ref_code,
                "user": user.email,
                "note": note_str
            })

            # 5. Update Reorder List (Handle partial vs full delivery)
            new_status = "received"
            reorder_id_target = item.reorder_id

            if not reorder_id_target:
                active_rl = local_db.execute(text("""
                    SELECT id FROM reorder_list
                    WHERE product_id = :pid AND status IN ('pending', 'partially_received', 'ordered')
                    ORDER BY id DESC LIMIT 1
                """), {"pid": prod_id}).fetchone()
                if active_rl:
                    reorder_id_target = active_rl[0]

            if reorder_id_target:
                rl_row = local_db.execute(text("""
                    SELECT selected_quantity, COALESCE(received_quantity, 0)
                    FROM reorder_list WHERE id = :rid
                """), {"rid": reorder_id_target}).fetchone()
                if rl_row:
                    requested_qty = float(rl_row[0] or 0)
                    prev_recv = float(rl_row[1] or 0)
                    cum_recv = prev_recv + recv_qty
                    if cum_recv >= requested_qty:
                        new_status = "received"
                    else:
                        new_status = "partially_received"

                    local_db.execute(text("""
                        UPDATE reorder_list
                        SET received_quantity = :cum_recv,
                            status = :st,
                            updated_at = NOW()
                        WHERE id = :rid
                    """), {
                        "cum_recv": cum_recv,
                        "st": new_status,
                        "rid": reorder_id_target
                    })

            received_summary.append({
                "product_id": prod_id,
                "product_name": prod_name,
                "received_quantity": recv_qty,
                "previous_stock": prev_stock,
                "new_stock": new_stock,
                "unit": unit or "unit",
                "batch_id": batch_id,
                "lot_number": lot_no,
                "serial_number": serial_no,
                "status": new_status,
                "barcode": barcode_val
            })

        local_db.commit()

        return {
            "status": "success",
            "message": f"Successfully received {len(received_summary)} item(s) ({total_qty_received} total units) into local stock.",
            "received_count": len(received_summary),
            "total_units": total_qty_received,
            "items": received_summary
        }

    except Exception as e:
        local_db.rollback()
        raise HTTPException(500, f"Stock receiving transaction failed and was rolled back: {str(e)}")


@router.post("/upload-wholesaler")
@limiter.limit("10/minute")
async def upload_wholesaler_document(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("reorder.create")),
    local_db: Session = Depends(get_local_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Wholesaler Document Ingestion Pipeline:
    1. Validates file format (.csv, .xlsx, .xls, .json, .txt, .pdf, .jpg, .png, .webp).
    2. Computes file hash to protect against duplicate deliveries (Section 52).
    3. Extracts line items, supplier, invoice, barcodes, serials, batch, expiry, sizes, colors.
    4. Matches items against catalog using strict priority:
       Barcode > SKU > Serial > Variant (Size/Color) > Exact Name > Fuzzy Match.
    5. Categorizes rows: 'matched', 'needs_review' (with candidate dropdown choices), 'not_found', 'invalid', 'duplicate'.
    6. Does NOT immediately modify stock — presents structured review preview for store manager confirmation.
    """
    file_bytes = await file.read()
    ext = validate_receipt_file(file, file_bytes)

    # 1. Compute file hash and check duplicate delivery
    file_hash = compute_file_hash(file_bytes)

    raw_text = ""
    if ext == ".pdf":
        raw_text = extract_text_from_pdf(file_bytes)
    elif ext == ".txt":
        raw_text = file_bytes.decode("utf-8", errors="ignore")

    business_type = getattr(user, "business_type_val", "grocery") or "grocery"
    extracted_data = parse_receipt_text_or_vision(
        raw_text=raw_text,
        filename=file.filename or f"wholesaler_doc{ext}",
        business_type=business_type,
        file_bytes=file_bytes
    )

    supplier_name = extracted_data.get("supplier_name", "Wholesaler")
    invoice_number = extracted_data.get("invoice_number", f"WS-{uuid.uuid4().hex[:6].upper()}")

    # Check duplicate delivery
    is_dup_delivery, dup_delivery_warning = check_duplicate_delivery(
        local_db=local_db,
        file_hash=file_hash,
        supplier_name=supplier_name,
        invoice_number=invoice_number
    )

    # Multi-signal catalog matching
    matched_items = match_items_with_catalogs(extracted_data.get("items", []), local_db, master_db)

    # Summary statistics for review preview modal
    matched_count = sum(1 for i in matched_items if i["status"] == "matched")
    review_count = sum(1 for i in matched_items if i["status"] == "needs_review")
    not_found_count = sum(1 for i in matched_items if i["status"] == "not_found")
    invalid_count = sum(1 for i in matched_items if i["status"] == "invalid")
    duplicate_count = sum(1 for i in matched_items if i["status"] == "duplicate")

    return {
        "status": "success",
        "filename": file.filename,
        "format": ext,
        "file_hash": file_hash,
        "duplicate_delivery_warning": dup_delivery_warning,
        "supplier_name": supplier_name,
        "invoice_number": invoice_number,
        "invoice_date": extracted_data.get("invoice_date", date.today().isoformat()),
        "subtotal": extracted_data.get("subtotal", 0.0),
        "total_amount": extracted_data.get("total_amount", 0.0),
        "items_count": len(matched_items),
        "summary": {
            "total_rows": len(matched_items),
            "matched": matched_count,
            "needs_review": review_count,
            "not_found": not_found_count,
            "invalid": invalid_count,
            "duplicates": duplicate_count,
            "ready_to_add": matched_count,
        },
        "items": matched_items
    }


@router.post("/confirm-wholesaler")
@limiter.limit("10/minute")
def confirm_wholesaler_into_stock(
    request: Request,
    body: WholesalerConfirmRequest,
    user: User = Depends(require_permission("reorder.create")),
    local_db: Session = Depends(get_local_db)
):
    """
    Final Wholesaler Stock Confirmation:
    - Server-authoritative transaction.
    - Adds verified quantities directly into products.current_stock.
    - Supports new product creation if requested ('Create New Product').
    - Creates inventory_batches with batch numbers, serial numbers, expiry dates.
    - Creates inventory_transactions for every line item.
    - Links and updates matching active reorders to 'received' or 'partially_received'.
    - Records purchase record and audit trail.
    """
    if not body.items:
        raise HTTPException(400, "No wholesaler items provided.")

    imported_count = 0
    total_qty = 0.0
    inv_num = body.invoice_number or f"WS-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
    sup_name = body.supplier_name or "Wholesaler"

    # Find or create supplier
    sup_row = local_db.execute(text("SELECT id FROM suppliers WHERE name = :name"), {"name": sup_name}).fetchone()
    if sup_row:
        supplier_id = sup_row[0]
    else:
        new_sup = local_db.execute(text("""
            INSERT INTO suppliers (name, contact_person, email)
            VALUES (:name, 'Accounts Dept', :email)
            RETURNING id
        """), {"name": sup_name, "email": user.email})
        supplier_id = new_sup.fetchone()[0]

    try:
        # Create purchase record
        subtotal = sum(float(i.quantity) * float(i.purchase_price or 0) for i in body.items)
        pur_res = local_db.execute(text("""
            INSERT INTO purchases (
                supplier_id, invoice_number, purchase_date,
                subtotal, gst_amount, total_amount, payment_status, source, created_at
            ) VALUES (
                :sid, :inv, CURRENT_DATE, :sub, 0, :sub, 'PAID', 'wholesaler_import', NOW()
            ) RETURNING id
        """), {"sid": supplier_id, "inv": inv_num, "sub": round(subtotal, 2)})
        purchase_id = pur_res.fetchone()[0]

        for idx, item in enumerate(body.items):
            raw_name = item.product_name.strip()
            qty = float(item.quantity)
            if qty <= 0:
                continue

            cost = float(item.purchase_price or 0.0)
            mrp = float(item.mrp) if item.mrp is not None else round(cost * 1.3, 2)
            barcode = clean_str_code(item.barcode)
            serial_no = clean_str_code(item.serial_number)
            lot_no = item.batch_number or serial_no or f"LOT-{datetime.utcnow().strftime('%Y%m%d%H%M')}-{idx+1}"

            exp_date_val = None
            if item.expiry_date:
                try:
                    exp_date_val = datetime.strptime(item.expiry_date[:10], "%Y-%m-%d").date()
                except Exception:
                    exp_date_val = None

            prod_id = item.product_id

            # If no product_id given, match by barcode or name
            if not prod_id and barcode:
                b_row = local_db.execute(text("SELECT id FROM products WHERE barcode = :bc"), {"bc": barcode}).fetchone()
                if b_row:
                    prod_id = b_row[0]

            if not prod_id:
                p_row = local_db.execute(text("SELECT id FROM products WHERE product_name ILIKE :name"), {"name": raw_name}).fetchone()
                if p_row:
                    prod_id = p_row[0]

            if prod_id:
                # Update existing product
                p_info = local_db.execute(
                    text("SELECT current_stock FROM products WHERE id = :id FOR UPDATE"),
                    {"id": prod_id}
                ).fetchone()
                prev_stock = float(p_info[0] or 0)
                new_stock = prev_stock + qty
                local_db.execute(text("""
                    UPDATE products
                    SET current_stock = :new_stock,
                        reorder_level = reorder_level + :received_quantity,
                        purchase_price = CASE WHEN :cost > 0 THEN :cost ELSE purchase_price END,
                        barcode = COALESCE(:bc, barcode),
                        size = COALESCE(:sz, size),
                        color = COALESCE(:clr, color),
                        updated_at = NOW()
                    WHERE id = :id
                """), {
                    "new_stock": new_stock,
                    "received_quantity": qty,
                    "cost": cost,
                    "bc": barcode,
                    "sz": item.size,
                    "clr": item.color,
                    "id": prod_id
                })
            else:
                # Create brand-new product from wholesaler
                sku_cand = f"SKU-{re.sub(r'[^A-Z0-9]', '', raw_name.upper())[:8]}-{uuid.uuid4().hex[:4].upper()}"
                new_p = local_db.execute(text("""
                    INSERT INTO products (
                        sku, barcode, product_name, current_stock, reorder_level,
                        selling_price, purchase_price, mrp, unit, size, color, style,
                        variant_name, supplier_id, status, created_at, updated_at
                    ) VALUES (
                        :sku, :bc, :name, :stock, 10,
                        :selling, :cost, :mrp, :unit, :sz, :clr, :sty,
                        :vname, :sid, 'active', NOW(), NOW()
                    ) RETURNING id
                """), {
                    "sku": sku_cand,
                    "bc": barcode or f"BAR-{sku_cand}",
                    "name": raw_name,
                    "stock": qty,
                    "selling": mrp,
                    "cost": cost,
                    "mrp": mrp,
                    "unit": item.unit or "unit",
                    "sz": item.size,
                    "clr": item.color,
                    "sty": item.style,
                    "vname": item.variant_name,
                    "sid": supplier_id
                })
                prod_id = new_p.fetchone()[0]
                prev_stock = 0.0
                new_stock = qty

            # Create Inventory Batch
            batch_res = local_db.execute(text("""
                INSERT INTO inventory_batches (
                    product_id, lot_number, serial_number, quantity, cost_price,
                    manufacturing_date, expiry_date, status, created_at
                ) VALUES (
                    :pid, :lot, :sn, :qty, :cost,
                    CURRENT_DATE, :exp, 'active', NOW()
                ) RETURNING id
            """), {
                "pid": prod_id,
                "lot": lot_no,
                "sn": serial_no,
                "qty": qty,
                "cost": cost,
                "exp": exp_date_val
            })
            batch_id = batch_res.fetchone()[0]

            # Record Inventory Transaction
            local_db.execute(text("""
                INSERT INTO inventory_transactions (
                    product_id, batch_id, transaction_type, quantity,
                    previous_stock, new_stock, reference_id, performed_by, note, timestamp
                ) VALUES (
                    :pid, :bid, 'Purchase', :qty,
                    :prev, :new, :ref, :user, :note, NOW()
                )
            """), {
                "pid": prod_id,
                "bid": batch_id,
                "qty": qty,
                "prev": prev_stock,
                "new": new_stock,
                "ref": inv_num,
                "user": user.email,
                "note": f"Wholesaler Delivery {inv_num} | S/N: {serial_no or '-'} | Barcode: {barcode or '-'}"
            })

            # Record purchase item
            local_db.execute(text("""
                INSERT INTO purchase_items (
                    purchase_id, product_id, product_name, quantity, unit,
                    unit_price, mrp, line_total, batch_number, expiry_date
                ) VALUES (
                    :pur_id, :pid, :name, :qty, :unit,
                    :price, :mrp, :tot, :batch, :exp
                )
            """), {
                "pur_id": purchase_id,
                "pid": prod_id,
                "name": raw_name,
                "qty": qty,
                "unit": item.unit or "unit",
                "price": cost,
                "mrp": mrp,
                "tot": round(qty * cost, 2),
                "batch": lot_no,
                "exp": exp_date_val
            })

            # Check if pending in reorder_list and mark received / partially_received
            rl_match = local_db.execute(text("""
                SELECT id, selected_quantity, COALESCE(received_quantity, 0)
                FROM reorder_list
                WHERE product_id = :pid AND status IN ('pending', 'partially_received', 'ordered')
                ORDER BY id DESC LIMIT 1
            """), {"pid": prod_id}).fetchone()

            if rl_match:
                req_qty = float(rl_match[1] or 0)
                prev_recv = float(rl_match[2] or 0)
                cum_recv = prev_recv + qty
                st = "received" if cum_recv >= req_qty else "partially_received"
                local_db.execute(text("""
                    UPDATE reorder_list
                    SET received_quantity = :cum, status = :st, updated_at = NOW()
                    WHERE id = :rid
                """), {"cum": cum_recv, "st": st, "rid": rl_match[0]})

            imported_count += 1
            total_qty += qty

        # Store import record with file_hash
        if body.file_hash:
            local_db.execute(text("""
                INSERT INTO receipt_imports (
                    file_name, file_hash, uploaded_by, supplier_id, supplier_name_extracted,
                    invoice_number, invoice_date, processing_status,
                    subtotal, total_amount, confirmed_at, confirmed_by, created_at
                ) VALUES (
                    :fname, :fhash, :user, :sid, :sname,
                    :inv, CURRENT_DATE, 'imported',
                    :sub, :sub, NOW(), :user, NOW()
                )
            """), {
                "fname": f"Delivery_{inv_num}.csv",
                "fhash": body.file_hash,
                "user": user.email,
                "sid": supplier_id,
                "sname": sup_name,
                "inv": inv_num,
                "sub": round(subtotal, 2)
            })

        # Store Audit Log
        local_db.execute(text("""
            INSERT INTO audit_logs (
                user_id, action, resource, resource_id, metadata, timestamp
            ) VALUES (
                :user, 'CONFIRMED_SUPPLIER_IMPORT', 'purchases', :res_id, :meta, NOW()
            )
        """), {
            "user": user.email,
            "res_id": str(purchase_id),
            "meta": json.dumps({
                "invoice_number": inv_num,
                "supplier": sup_name,
                "items_count": imported_count,
                "total_units": total_qty,
                "subtotal": round(subtotal, 2)
            })
        })

        local_db.commit()

        return {
            "status": "success",
            "message": f"Successfully added {imported_count} item(s) ({int(total_qty) if total_qty.is_integer() else total_qty} total units) from supplier into local stock.",
            "imported_count": imported_count,
            "total_units": total_qty,
            "invoice_number": inv_num,
            "purchase_id": purchase_id
        }

    except Exception as e:
        local_db.rollback()
        raise HTTPException(500, f"Wholesaler stock confirmation failed: {str(e)}")


@router.get("/history")
def get_reorder_and_receiving_history(
    q: Optional[str] = Query(None, description="Search by product name, SKU, or barcode"),
    status: Optional[str] = Query(None, description="Filter reorder status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("reorder.view")),
    local_db: Session = Depends(get_local_db)
):
    """
    Historical view for Reorders and Physical Stock Receipts (Sections 29 & 50):
    Allows store managers to audit:
    - Reorder History (Date, Product, Requested Qty, Received Qty, Supplier, Status, Reasons)
    - Receiving History / Stock Transactions (Transaction ID, Product, Prev/New Stock, Units, Lots, Serials, Performer)
    """
    term_filter = ""
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    if q and q.strip():
        term_filter = "AND (p.product_name ILIKE :term OR p.sku ILIKE :term OR p.barcode ILIKE :term)"
        params["term"] = f"%{q.strip()}%"

    status_filter = ""
    if status and status.strip():
        status_filter = "AND rl.status = :status_val"
        params["status_val"] = status.strip()

    reorder_sql = f"""
        SELECT rl.id, rl.product_id, p.product_name, p.sku, p.barcode,
               rl.selected_quantity as requested_quantity,
               COALESCE(rl.received_quantity, 0) as received_quantity,
               p.unit, COALESCE(s.name, 'Default Supplier') as supplier_name,
               rl.status, rl.reason, rl.created_at, rl.updated_at,
               p.size, p.color, p.style, p.variant_name, rl.notes
        FROM reorder_list rl
        JOIN products p ON rl.product_id = p.id
        LEFT JOIN suppliers s ON rl.supplier_id = s.id
        WHERE 1=1 {term_filter} {status_filter}
        ORDER BY rl.updated_at DESC
        LIMIT :limit OFFSET :offset
    """
    reorder_rows = local_db.execute(text(reorder_sql), params).fetchall()

    reorders_list = [{
        "id": r[0],
        "product_id": r[1],
        "product_name": r[2],
        "sku": r[3],
        "barcode": r[4],
        "requested_quantity": float(r[5] or 0),
        "received_quantity": float(r[6] or 0),
        "remaining_quantity": max(float(r[5] or 0) - float(r[6] or 0), 0.0),
        "unit": r[7] or "unit",
        "supplier_name": r[8],
        "status": r[9],
        "reason": r[10],
        "reorder_date": r[11].isoformat() if r[11] else None,
        "updated_at": r[12].isoformat() if r[12] else None,
        "size": r[13],
        "color": r[14],
        "style": r[15],
        "variant_name": r[16],
        "notes": r[17],
    } for r in reorder_rows]

    # Receiving transactions history
    recv_sql = f"""
        SELECT it.id, it.product_id, p.product_name, p.sku, p.barcode,
               it.previous_stock, it.quantity as received_quantity, it.new_stock,
               p.unit, ib.lot_number, ib.serial_number, ib.expiry_date,
               it.performed_by, it.reference_id, it.note, it.timestamp,
               it.transaction_type, p.size, p.color
        FROM inventory_transactions it
        JOIN products p ON it.product_id = p.id
        LEFT JOIN inventory_batches ib ON it.batch_id = ib.id
        WHERE it.transaction_type IN ('REORDER_RECEIVED', 'Purchase')
          {term_filter}
        ORDER BY it.timestamp DESC
        LIMIT :limit OFFSET :offset
    """
    recv_rows = local_db.execute(text(recv_sql), params).fetchall()

    receipts_list = [{
        "id": r[0],
        "product_id": r[1],
        "product_name": r[2],
        "sku": r[3],
        "barcode": r[4],
        "previous_stock": float(r[5] or 0),
        "received_quantity": float(r[6] or 0),
        "new_stock": float(r[7] or 0),
        "unit": r[8] or "unit",
        "lot_number": r[9],
        "serial_number": r[10],
        "expiry_date": r[11].isoformat() if r[11] else None,
        "performed_by": r[12],
        "transaction_id": r[13] or f"TX-{r[0]}",
        "note": r[14],
        "received_at": r[15].isoformat() if r[15] else None,
        "source": r[16],
        "size": r[17],
        "color": r[18]
    } for r in recv_rows]

    return {
        "reorders": reorders_list,
        "receipts": receipts_list,
        "count_reorders": len(reorders_list),
        "count_receipts": len(receipts_list)
    }



@router.post("/create-po")
@limiter.limit("15/minute")
def create_purchase_order_from_reorder(
    request: Request,
    body: CreatePOFromReorderInput,
    user: User = Depends(require_permission("orders.create")),
    local_db: Session = Depends(get_local_db)
):
    """Generate an official Purchase Order from selected reorder items and mark status as ordered."""
    if not body.reorder_item_ids:
        raise HTTPException(400, "Please select at least one reorder item.")

    items = local_db.execute(text("""
        SELECT rl.id, rl.product_id, p.product_name,
               GREATEST(rl.selected_quantity - COALESCE(rl.received_quantity, 0), 0) as remaining_qty,
               p.purchase_price
        FROM reorder_list rl
        JOIN products p ON rl.product_id = p.id
        WHERE rl.id = ANY(:ids)
    """), {"ids": body.reorder_item_ids}).fetchall()

    if not items:
        raise HTTPException(404, "No matching reorder items found.")

    po_number = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    total_amount = sum(float(i[3] or 0) * float(i[4] or 0) for i in items)

    po_res = local_db.execute(text("""
        INSERT INTO purchase_orders (
            po_number, supplier_id, status, total_amount, expected_delivery, created_by
        ) VALUES (
            :po_num, :sid, 'draft', :tot, :exp, :user
        ) RETURNING id
    """), {
        "po_num": po_number,
        "sid": body.supplier_id,
        "tot": round(total_amount, 2),
        "exp": body.expected_delivery if body.expected_delivery else (date.today() + timedelta(days=5)).isoformat(),
        "user": user.email,
    })
    po_id = po_res.fetchone()[0]

    for item in items:
        rl_id, prod_id, prod_name, qty, cost = item
        line_total = float(qty) * float(cost)
        local_db.execute(text("""
            INSERT INTO purchase_order_items (
                purchase_order_id, product_id, product_name, quantity, unit_price, line_total
            ) VALUES (
                :po_id, :pid, :name, :qty, :cost, :tot
            )
        """), {
            "po_id": po_id,
            "pid": prod_id,
            "name": prod_name,
            "qty": qty,
            "cost": cost,
            "tot": round(line_total, 2)
        })

    local_db.execute(text("""
        UPDATE reorder_list
        SET status = 'ordered', updated_at = NOW()
        WHERE id = ANY(:ids)
    """), {"ids": body.reorder_item_ids})

    local_db.commit()

    return {
        "message": f"Purchase Order {po_number} created successfully.",
        "purchase_order_id": po_id,
        "po_number": po_number,
        "total_amount": round(total_amount, 2),
        "items_count": len(items)
    }


@router.post("/reorder-previous/{purchase_id}")
@limiter.limit("15/minute")
def reorder_from_previous_purchase(
    request: Request,
    purchase_id: int,
    user: User = Depends(require_permission("orders.create")),
    local_db: Session = Depends(get_local_db)
):
    """Auto-populates a new draft purchase order from a previous purchase history record."""
    pur = local_db.execute(text("""
        SELECT id, supplier_id, invoice_number, total_amount
        FROM purchases WHERE id = :id
    """), {"id": purchase_id}).fetchone()

    if not pur:
        raise HTTPException(404, "Previous purchase record not found.")

    items = local_db.execute(text("""
        SELECT product_id, product_name, quantity, unit_price
        FROM purchase_items WHERE purchase_id = :id
    """), {"id": purchase_id}).fetchall()

    if not items:
        raise HTTPException(400, "Purchase record has no items to reorder.")

    po_number = f"PO-RE-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    total_amount = sum(float(i[2] or 0) * float(i[3] or 0) for i in items)

    po_res = local_db.execute(text("""
        INSERT INTO purchase_orders (
            po_number, supplier_id, status, total_amount, expected_delivery, created_by
        ) VALUES (
            :po_num, :sid, 'draft', :tot, :exp, :user
        ) RETURNING id
    """), {
        "po_num": po_number,
        "sid": pur[1],
        "tot": round(total_amount, 2),
        "exp": (date.today() + timedelta(days=4)).isoformat(),
        "user": user.email
    })
    po_id = po_res.fetchone()[0]

    for item in items:
        pid, pname, qty, price = item
        local_db.execute(text("""
            INSERT INTO purchase_order_items (
                purchase_order_id, product_id, product_name, quantity, unit_price, line_total
            ) VALUES (
                :po_id, :pid, :name, :qty, :cost, :tot
            )
        """), {
            "po_id": po_id,
            "pid": pid,
            "name": pname,
            "qty": qty,
            "cost": price,
            "tot": round(float(qty) * float(price), 2)
        })

    local_db.commit()

    return {
        "message": f"Generated reorder PO {po_number} from previous purchase.",
        "purchase_order_id": po_id,
        "po_number": po_number,
        "total_amount": round(total_amount, 2),
        "items_count": len(items)
    }


