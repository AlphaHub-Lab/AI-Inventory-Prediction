"""
Master Catalog & Local Store Product Synchronization Router
Enables:
- Searching Local DB and Master DB seamlessly
- 1-click importing master products into the business's dedicated local database
- Avoiding duplicating the entire master catalog: only required products are imported locally
"""

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_local_db, get_master_db, require_permission
from ..models import User
from ..rate_limit import limiter

router = APIRouter(prefix="/api/catalog", tags=["Master Catalog"])


class ImportProductInput(BaseModel):
    master_product_id: str
    selling_price: float = Field(ge=0)
    purchase_price: float = Field(ge=0)
    mrp: Optional[float] = None
    initial_stock: float = Field(default=0.0, ge=0)
    reorder_level: float = Field(default=10.0, ge=0)
    supplier_id: Optional[int] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None


@router.get("/search")
def search_catalog_products(
    q: str = Query(..., min_length=1),
    category: Optional[str] = None,
    user: User = Depends(get_current_user),
    local_db: Session = Depends(get_local_db),
    master_db: Session = Depends(get_master_db),
):
    """
    Search Local DB and Master DB.
    Returns:
    - local_results: products already stocked in the business
    - master_results: products available in the business type's global catalog to import
    """
    query_term = f"%{q.strip()}%"

    # 1. Search Local DB
    local_sql = """
        SELECT id, master_product_id, sku, barcode, product_name, brand, category,
               current_stock, reorder_level, selling_price, purchase_price, mrp, status
        FROM products
        WHERE (product_name ILIKE :q OR sku ILIKE :q OR barcode ILIKE :q OR brand ILIKE :q)
    """
    params: Dict[str, Any] = {"q": query_term}
    if category:
        local_sql += " AND category ILIKE :cat"
        params["cat"] = f"%{category.strip()}%"
    local_sql += " LIMIT 25"

    local_rows = local_db.execute(text(local_sql), params).fetchall()
    local_results = [{
        "id": r[0],
        "master_product_id": r[1],
        "sku": r[2],
        "barcode": r[3],
        "product_name": r[4],
        "brand": r[5],
        "category": r[6],
        "current_stock": float(r[7] or 0),
        "reorder_level": float(r[8] or 0),
        "selling_price": float(r[9] or 0),
        "purchase_price": float(r[10] or 0),
        "mrp": float(r[11]) if r[11] is not None else None,
        "status": r[12],
        "is_local": True
    } for r in local_rows]

    # Keep track of master IDs already imported locally
    imported_master_ids = {str(r[1]) for r in local_rows if r[1]}

    # 2. Search Master DB
    master_sql = """
        SELECT id, sku, barcode, product_name, brand, category, subcategory, description
        FROM catalog.products
        WHERE (product_name ILIKE :q OR sku ILIKE :q OR barcode ILIKE :q OR brand ILIKE :q)
    """
    m_params: Dict[str, Any] = {"q": query_term}
    if category:
        master_sql += " AND category ILIKE :cat"
        m_params["cat"] = f"%{category.strip()}%"
    master_sql += " LIMIT 35"

    master_rows = master_db.execute(text(master_sql), m_params).fetchall()
    master_results = []

    for r in master_rows:
        m_id_str = str(r[0])
        # If already in local DB, mark as imported
        is_imported = m_id_str in imported_master_ids
        master_results.append({
            "master_id": m_id_str,
            "sku": r[1],
            "barcode": r[2],
            "product_name": r[3],
            "brand": r[4],
            "category": r[5],
            "subcategory": r[6],
            "description": r[7],
            "already_imported": is_imported,
            "is_local": False
        })

    return {
        "query": q,
        "business_type": getattr(user, "business_type_val", "unknown"),
        "local_count": len(local_results),
        "master_count": len(master_results),
        "local_products": local_results,
        "master_products": master_results
    }


@router.post("/import", status_code=201)
@limiter.limit("15/minute")
def import_master_product(
    request: Request,
    body: ImportProductInput,
    user: User = Depends(require_permission("inventory.create")),
    local_db: Session = Depends(get_local_db),
    master_db: Session = Depends(get_master_db),
):
    """
    Import a single product from the Master Database into the local business database.
    Does NOT copy the whole catalog - only imports the specific required product.
    Store sets its own store selling price, purchase price, initial stock, and supplier.
    """
    # 1. Fetch from Master DB
    m_row = master_db.execute(text("""
        SELECT id, sku, barcode, product_name, brand, category, subcategory, description
        FROM catalog.products
        WHERE id::text = :id OR sku = :id
    """), {"id": body.master_product_id}).fetchone()

    if not m_row:
        raise HTTPException(404, "Product not found in the master catalog.")

    m_id, m_sku, m_barcode, m_name, m_brand, m_cat, m_subcat, m_desc = m_row

    # Check if already imported
    existing = local_db.execute(
        text("SELECT id, product_name FROM products WHERE master_product_id = :mid OR sku = :sku"),
        {"mid": str(m_id), "sku": m_sku}
    ).fetchone()

    if existing:
        raise HTTPException(409, f"Product '{existing[1]}' is already present in your local inventory (ID: {existing[0]}).")

    mrp_val = body.mrp if body.mrp is not None else round(body.selling_price * 1.05, 2)

    # Specific metadata query from master DB if medical, dairy, etc.
    b_type = getattr(user, "business_type_val", "grocery")
    gen_name, form, strg, mfg, rx = None, None, None, None, False
    exp_req, st_temp, shelf_l = False, None, None

    if b_type == "medical":
        med = master_db.execute(text("""
            SELECT generic_name, dosage_form, strength, manufacturer, prescription_required
            FROM catalog.medical_product_details WHERE product_id::text = :id
        """), {"id": str(m_id)}).fetchone()
        if med:
            gen_name, form, strg, mfg, rx = med[0], med[1], med[2], med[3], bool(med[4])
    elif b_type == "dairy":
        dry = master_db.execute(text("""
            SELECT expiry_required, storage_temperature, shelf_life
            FROM catalog.dairy_product_details WHERE product_id::text = :id
        """), {"id": str(m_id)}).fetchone()
        if dry:
            exp_req, st_temp, shelf_l = bool(dry[0]), dry[1], dry[2]

    # Insert into local products
    ins = local_db.execute(text("""
        INSERT INTO products (
            master_product_id, sku, barcode, product_name, brand, category, subcategory,
            current_stock, reorder_level, minimum_stock, maximum_stock,
            selling_price, purchase_price, mrp, gst_percentage, supplier_id, status,
            generic_name, dosage_form, strength, manufacturer, prescription_required,
            expiry_required, storage_temperature, shelf_life
        ) VALUES (
            :mid, :sku, :barcode, :name, :brand, :cat, :subcat,
            :stock, :rlevel, 5, 500,
            :sell, :cost, :mrp, 12.0, :sup_id, 'active',
            :gen, :form, :strg, :mfg, :rx,
            :exp_req, :st_temp, :shelf_l
        ) RETURNING id
    """), {
        "mid": str(m_id),
        "sku": m_sku,
        "barcode": m_barcode or f"BAR-{m_sku}",
        "name": m_name,
        "brand": m_brand,
        "cat": m_cat,
        "subcat": m_subcat,
        "stock": body.initial_stock,
        "rlevel": body.reorder_level,
        "sell": body.selling_price,
        "cost": body.purchase_price,
        "mrp": mrp_val,
        "sup_id": body.supplier_id,
        "gen": gen_name,
        "form": form,
        "strg": strg,
        "mfg": mfg,
        "rx": rx,
        "exp_req": exp_req,
        "st_temp": st_temp,
        "shelf_l": shelf_l
    })
    new_id = ins.fetchone()[0]

    # If initial stock > 0, create batch and transaction
    if body.initial_stock > 0:
        lot = body.batch_number or f"LOT-IMP-{uuid.uuid4().hex[:6].upper()}"
        local_db.execute(text("""
            INSERT INTO inventory_batches (
                product_id, lot_number, quantity, cost_price, manufacturing_date, expiry_date, status
            ) VALUES (
                :pid, :lot, :qty, :cost, CURRENT_DATE, :exp, 'active'
            )
        """), {
            "pid": new_id,
            "lot": lot,
            "qty": body.initial_stock,
            "cost": body.purchase_price,
            "exp": body.expiry_date if body.expiry_date else None,
        })

        local_db.execute(text("""
            INSERT INTO inventory_transactions (
                product_id, transaction_type, quantity, previous_stock, new_stock,
                reference_id, performed_by, note
            ) VALUES (
                :pid, 'Purchase', :qty, 0, :qty,
                :ref, :user, 'Initial stock on master product import'
            )
        """), {
            "pid": new_id,
            "qty": body.initial_stock,
            "ref": f"IMP-{new_id}",
            "user": user.email
        })

    # Log in audit log
    local_db.execute(text("""
        INSERT INTO audit_logs (user_id, action, resource, resource_id, metadata)
        VALUES (:user, 'PRODUCT_IMPORTED', 'products', :pid, :meta)
    """), {
        "user": user.email,
        "pid": str(new_id),
        "meta": '{"master_id": "' + str(m_id) + '", "product_name": "' + m_name + '"}'
    })

    local_db.commit()

    return {
        "message": f"Successfully imported '{m_name}' to local inventory.",
        "product_id": new_id,
        "product_name": m_name,
        "sku": m_sku,
        "current_stock": body.initial_stock,
        "selling_price": body.selling_price
    }
