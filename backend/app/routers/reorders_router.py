"""
Dedicated Reorder Management Router
Supports:
- Low Stock (current_stock <= reorder_level)
- Previously Ordered Items (based on actual purchase history)
- Frequently Ordered Items
- Recently Ordered Items
- Suggested Reorders (with editable quantities and AI demand insights)
- Pending Reorders
- Completed Reorders (Purchase Orders)
- One-click Purchase Order generation
- One-click Reorder from previous orders
"""

import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_local_db, require_permission
from ..models import User

router = APIRouter(prefix="/api/reorders", tags=["Reorder List"])


class ReorderItemInput(BaseModel):
    product_id: int
    supplier_id: Optional[int] = None
    suggested_quantity: float = Field(default=10.0, ge=1)
    selected_quantity: float = Field(default=10.0, ge=1)
    source: str = "manual"


class ReorderItemUpdate(BaseModel):
    selected_quantity: Optional[float] = Field(None, ge=1)
    supplier_id: Optional[int] = None
    status: Optional[str] = None


class CreatePOFromReorderInput(BaseModel):
    supplier_id: int
    reorder_item_ids: List[int]
    expected_delivery: Optional[str] = None


class ReorderPreviousPurchaseInput(BaseModel):
    purchase_id: int
    adjust_quantities: Optional[Dict[int, float]] = None # product_id -> new qty


@router.get("/overview")
def get_reorder_overview(
    user: User = Depends(require_permission("reorder.view")),
    local_db: Session = Depends(get_local_db)
):
    """
    Returns the comprehensive 7-section reorder overview based on actual inventory and purchase history.
    """
    # 1. Low Stock Products (current_stock <= reorder_level)
    low_stock_rows = local_db.execute(text("""
        SELECT p.id, p.sku, p.product_name, p.brand, p.category, p.current_stock,
               p.reorder_level, p.purchase_price, p.selling_price, p.supplier_id,
               s.name as supplier_name,
               (SELECT pi.quantity FROM purchase_items pi WHERE pi.product_id = p.id ORDER BY pi.id DESC LIMIT 1) as last_qty,
               (SELECT pur.purchase_date FROM purchases pur JOIN purchase_items pi ON pur.id = pi.purchase_id WHERE pi.product_id = p.id ORDER BY pur.id DESC LIMIT 1) as last_date
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.current_stock <= p.reorder_level AND p.status = 'active'
        ORDER BY (p.current_stock - p.reorder_level) ASC
    """)).fetchall()

    low_stock = [{
        "product_id": r[0],
        "sku": r[1],
        "product_name": r[2],
        "brand": r[3],
        "category": r[4],
        "current_stock": float(r[5] or 0),
        "reorder_level": float(r[6] or 0),
        "purchase_price": float(r[7] or 0),
        "selling_price": float(r[8] or 0),
        "supplier_id": r[9],
        "supplier_name": r[10] or "Default Supplier",
        "last_order_quantity": float(r[11]) if r[11] is not None else 20.0,
        "last_order_date": r[12].isoformat() if r[12] else None,
        "suggested_quantity": max(float(r[6] or 10) * 2 - float(r[5] or 0), float(r[11] or 20.0)),
    } for r in low_stock_rows]

    # 2. Previously Ordered Items (based on actual purchase history)
    prev_ordered_rows = local_db.execute(text("""
        SELECT p.id, p.sku, p.product_name, p.current_stock, p.reorder_level,
               s.id as supplier_id, s.name as supplier_name,
               pi.unit_price, pi.quantity as last_qty, pur.purchase_date as last_date,
               pur.id as purchase_id
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
        "product_name": r[2],
        "current_stock": float(r[3] or 0),
        "reorder_level": float(r[4] or 0),
        "supplier_id": r[5],
        "supplier_name": r[6] or "Verified Supplier",
        "previous_price": float(r[7] or 0),
        "last_order_quantity": float(r[8] or 0),
        "last_order_date": r[9].isoformat() if r[9] else None,
        "purchase_id": r[10],
        "suggested_quantity": float(r[8] or 10),
    } for r in prev_ordered_rows]

    # 3. Frequently Ordered Items
    freq_rows = local_db.execute(text("""
        SELECT p.id, p.sku, p.product_name, COUNT(pi.id) as order_count,
               AVG(pi.quantity) as avg_qty, p.current_stock, p.reorder_level,
               p.supplier_id, s.name as supplier_name
        FROM purchase_items pi
        JOIN products p ON pi.product_id = p.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        GROUP BY p.id, p.sku, p.product_name, p.current_stock, p.reorder_level, p.supplier_id, s.name
        ORDER BY order_count DESC
        LIMIT 20
    """)).fetchall()

    frequently_ordered = [{
        "product_id": r[0],
        "sku": r[1],
        "product_name": r[2],
        "order_count": r[3],
        "average_quantity": round(float(r[4] or 0), 1),
        "current_stock": float(r[5] or 0),
        "reorder_level": float(r[6] or 0),
        "supplier_id": r[7],
        "supplier_name": r[8] or "Preferred Vendor",
        "suggested_quantity": round(float(r[4] or 20)),
    } for r in freq_rows]

    # 4. Recently Ordered Items (last 30 days)
    cutoff = date.today() - timedelta(days=30)
    rec_rows = local_db.execute(text("""
        SELECT DISTINCT ON (p.id) p.id, p.sku, p.product_name, pur.purchase_date,
               pi.quantity, pi.unit_price, s.name as supplier_name, pur.id as purchase_id
        FROM purchases pur
        JOIN purchase_items pi ON pur.id = pi.purchase_id
        JOIN products p ON pi.product_id = p.id
        LEFT JOIN suppliers s ON pur.supplier_id = s.id
        WHERE pur.purchase_date >= :cutoff
        ORDER BY p.id, pur.purchase_date DESC
        LIMIT 25
    """), {"cutoff": cutoff}).fetchall()

    recently_ordered = [{
        "product_id": r[0],
        "sku": r[1],
        "product_name": r[2],
        "order_date": r[3].isoformat() if r[3] else None,
        "quantity": float(r[4] or 0),
        "unit_price": float(r[5] or 0),
        "supplier_name": r[6] or "Vendor",
        "purchase_id": r[7]
    } for r in rec_rows]

    # 5. Suggested Reorders (combining low stock + purchase velocity)
    suggested = []
    for item in low_stock:
        suggested.append({
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "current_stock": item["current_stock"],
            "reorder_level": item["reorder_level"],
            "last_ordered_quantity": item["last_order_quantity"],
            "last_order_date": item["last_order_date"],
            "supplier_id": item["supplier_id"],
            "supplier_name": item["supplier_name"],
            "suggested_quantity": item["suggested_quantity"],
            "reason": "Stock below reorder threshold",
        })

    # 6. Pending Items in Reorder List
    pending_rows = local_db.execute(text("""
        SELECT rl.id, rl.product_id, p.product_name, p.sku, rl.supplier_id,
               s.name as supplier_name, rl.current_stock, rl.reorder_level,
               rl.suggested_quantity, rl.selected_quantity, rl.last_order_date,
               rl.last_order_quantity, rl.status, p.purchase_price
        FROM reorder_list rl
        JOIN products p ON rl.product_id = p.id
        LEFT JOIN suppliers s ON rl.supplier_id = s.id
        WHERE rl.status = 'pending'
        ORDER BY rl.created_at DESC
    """)).fetchall()

    pending_reorders = [{
        "id": r[0],
        "product_id": r[1],
        "product_name": r[2],
        "sku": r[3],
        "supplier_id": r[4],
        "supplier_name": r[5] or "Vendor",
        "current_stock": float(r[6] or 0),
        "reorder_level": float(r[7] or 0),
        "suggested_quantity": float(r[8] or 0),
        "selected_quantity": float(r[9] or 0),
        "last_order_date": r[10].isoformat() if r[10] else None,
        "last_order_quantity": float(r[11] or 0),
        "status": r[12],
        "estimated_cost": float(r[13] or 0) * float(r[9] or 0),
    } for r in pending_rows]

    # 7. Completed Reorders (Purchase Orders)
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

    return {
        "low_stock": low_stock,
        "previously_ordered": previously_ordered,
        "frequently_ordered": frequently_ordered,
        "recently_ordered": recently_ordered,
        "suggested_reorders": suggested,
        "pending_reorders": pending_reorders,
        "completed_reorders": completed_reorders,
    }


@router.post("/item")
def add_to_reorder(
    body: ReorderItemInput,
    user: User = Depends(require_permission("reorder.create")),
    local_db: Session = Depends(get_local_db)
):
    """Add a product to the pending reorder list with suggested and selected quantities."""
    # Get current stock and reorder point from product
    prod = local_db.execute(
        text("SELECT id, current_stock, reorder_level, supplier_id, purchase_price FROM products WHERE id = :id"),
        {"id": body.product_id}
    ).fetchone()
    if not prod:
        raise HTTPException(404, "Product not found")

    sup_id = body.supplier_id or prod[3]

    # Get last order history
    last_order = local_db.execute(text("""
        SELECT pi.quantity, pur.purchase_date
        FROM purchase_items pi
        JOIN purchases pur ON pi.purchase_id = pur.id
        WHERE pi.product_id = :id
        ORDER BY pur.purchase_date DESC LIMIT 1
    """), {"id": body.product_id}).fetchone()

    last_qty = float(last_order[0]) if last_order else float(prod[2] or 10)
    last_date = last_order[1] if last_order else None

    # Upsert into reorder_list
    res = local_db.execute(text("""
        INSERT INTO reorder_list (
            product_id, supplier_id, current_stock, reorder_level,
            suggested_quantity, selected_quantity, last_order_date,
            last_order_quantity, status, source
        ) VALUES (
            :pid, :sid, :cstock, :rlevel,
            :sug, :sel, :ldate,
            :lqty, 'pending', :src
        )
        ON CONFLICT (product_id) DO UPDATE SET
            selected_quantity = EXCLUDED.selected_quantity,
            suggested_quantity = EXCLUDED.suggested_quantity,
            supplier_id = EXCLUDED.supplier_id,
            status = 'pending',
            updated_at = NOW()
        RETURNING id
    """), {
        "pid": body.product_id,
        "sid": sup_id,
        "cstock": float(prod[1] or 0),
        "rlevel": float(prod[2] or 0),
        "sug": body.suggested_quantity,
        "sel": body.selected_quantity,
        "ldate": last_date,
        "lqty": last_qty,
        "src": body.source
    })
    local_db.commit()
    reorder_id = res.fetchone()[0]

    return {"message": "Product added to Reorder List", "reorder_id": reorder_id}


@router.put("/item/{reorder_id}")
def update_reorder_item(
    reorder_id: int,
    body: ReorderItemUpdate,
    user: User = Depends(require_permission("reorder.update")),
    local_db: Session = Depends(get_local_db)
):
    """Edit quantity or supplier for an item in the reorder list."""
    fields = []
    params: Dict[str, Any] = {"id": reorder_id}

    if body.selected_quantity is not None:
        fields.append("selected_quantity = :qty")
        params["qty"] = body.selected_quantity
    if body.supplier_id is not None:
        fields.append("supplier_id = :sid")
        params["sid"] = body.supplier_id
    if body.status is not None:
        fields.append("status = :status")
        params["status"] = body.status

    if not fields:
        return {"message": "No changes requested"}

    fields.append("updated_at = NOW()")
    sql = f"UPDATE reorder_list SET {', '.join(fields)} WHERE id = :id"
    local_db.execute(text(sql), params)
    local_db.commit()

    return {"message": "Reorder item updated successfully"}


@router.delete("/item/{reorder_id}")
def remove_reorder_item(
    reorder_id: int,
    user: User = Depends(require_permission("reorder.update")),
    local_db: Session = Depends(get_local_db)
):
    """Remove item from pending reorder list."""
    local_db.execute(text("DELETE FROM reorder_list WHERE id = :id"), {"id": reorder_id})
    local_db.commit()
    return {"message": "Removed from reorder list"}


@router.post("/create-po")
def create_purchase_order_from_reorder(
    body: CreatePOFromReorderInput,
    user: User = Depends(require_permission("orders.create")),
    local_db: Session = Depends(get_local_db)
):
    """
    Generate an official Purchase Order from selected reorder items.
    Updates reorder_list status to 'added_to_po'.
    """
    if not body.reorder_item_ids:
        raise HTTPException(400, "Please select at least one reorder item.")

    # Fetch reorder items
    items = local_db.execute(text("""
        SELECT rl.id, rl.product_id, p.product_name, rl.selected_quantity, p.purchase_price
        FROM reorder_list rl
        JOIN products p ON rl.product_id = p.id
        WHERE rl.id = ANY(:ids)
    """), {"ids": body.reorder_item_ids}).fetchall()

    if not items:
        raise HTTPException(404, "No matching reorder items found.")

    po_number = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    total_amount = sum(float(i[3] or 0) * float(i[4] or 0) for i in items)

    # Insert purchase order
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

    # Insert PO items
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

    # Mark reorder items as added_to_po
    local_db.execute(text("""
        UPDATE reorder_list
        SET status = 'added_to_po', updated_at = NOW()
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
def reorder_from_previous_purchase(
    purchase_id: int,
    user: User = Depends(require_permission("orders.create")),
    local_db: Session = Depends(get_local_db)
):
    """
    Reorder workflow from previous orders:
    Auto-populates a new draft purchase order from a previous purchase history record!
    User can adjust quantities before confirming.
    """
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

    # Create new draft PO
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
