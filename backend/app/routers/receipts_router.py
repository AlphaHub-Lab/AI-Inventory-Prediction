"""
Receipt & Invoice AI Processing Endpoints
Restricted operational exception: Available to Administrator, Business Owner,
and Associate (only when receipt permissions are explicitly granted).
"""

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database_manager import get_admin_session, get_local_session, get_master_session
from ..dependencies import get_admin_db, get_current_user, get_local_db, get_master_db, require_receipt_ai
from ..models import User
from ..rate_limit import limiter
from ..services.receipt_service import (
    execute_atomic_receipt_confirmation,
    extract_text_from_pdf,
    match_items_with_catalogs,
    parse_receipt_text_or_vision,
    save_receipt_import,
    validate_receipt_file
)

router = APIRouter(prefix="/api/receipts", tags=["Receipt AI"])


class ReceiptItemUpdate(BaseModel):
    id: Optional[int] = None
    raw_product_name: str
    matched_product_id: Optional[int] = None
    master_product_id: Optional[str] = None
    quantity: float = Field(gt=0, default=1.0)
    unit: str = "unit"
    barcode: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_price: float = Field(ge=0, default=0.0)
    mrp: Optional[float] = None
    gst_percentage: float = Field(ge=0, le=100, default=5.0)
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None
    confidence_score: Optional[float] = 0.0
    confidence_level: Optional[str] = "UNKNOWN"
    review_status: str = "verified"


class ReceiptConfirmPayload(BaseModel):
    supplier_name: str
    supplier_gstin: Optional[str] = None
    invoice_number: str
    invoice_date: Optional[str] = None
    items: List[ReceiptItemUpdate]


@router.post("/upload", status_code=201)
@limiter.limit("10/minute")
async def upload_and_process_receipt(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_receipt_ai),
    local_db: Session = Depends(get_local_db),
    master_db: Session = Depends(get_master_db),
):
    """
    Upload a receipt image, PDF, CSV, Excel, or text invoice.
    Validates file, extracts text/data via OCR/Vision/Spreadsheet pipeline,
    fuzzy-matches products against Local and Master databases (with Barcode priority),
    and stages the receipt in review_required status for human verification.
    """
    file_bytes = await file.read()
    ext = validate_receipt_file(file, file_bytes)

    # Extract text if PDF, or let parser handle layout heuristics
    raw_text = ""
    if ext == ".pdf":
        raw_text = extract_text_from_pdf(file_bytes)

    business_type = getattr(user, "business_type_val", "grocery") or "grocery"
    parsed_data = parse_receipt_text_or_vision(raw_text, file.filename or "receipt", business_type, file_bytes=file_bytes)

    # Multi-signal matching against local DB and master DB
    matched_items = match_items_with_catalogs(parsed_data["items"], local_db, master_db)

    # Save to local database in review_required state
    import_id = save_receipt_import(
        local_db=local_db,
        filename=file.filename or "uploaded_receipt",
        uploaded_by=user.email,
        parsed_data=parsed_data,
        matched_items=matched_items
    )

    return {
        "import_id": import_id,
        "file_name": file.filename,
        "processing_status": "review_required",
        "supplier": {
            "name": parsed_data.get("supplier_name"),
            "gstin": parsed_data.get("supplier_gstin"),
        },
        "invoice": {
            "number": parsed_data.get("invoice_number"),
            "date": parsed_data.get("invoice_date"),
        },
        "totals": {
            "subtotal": parsed_data.get("subtotal"),
            "gst_amount": parsed_data.get("gst_amount"),
            "grand_total": parsed_data.get("grand_total"),
        },
        "items": matched_items,
        "message": "Receipt processed successfully. Please review and verify items before confirmation."
    }


@router.get("")
def list_receipt_imports(
    user: User = Depends(require_receipt_ai),
    local_db: Session = Depends(get_local_db)
):
    """List all receipt imports with statuses and totals for the current business."""
    rows = local_db.execute(text("""
        SELECT id, file_name, uploaded_by, supplier_name_extracted,
               invoice_number, invoice_date, processing_status,
               subtotal, gst_amount, total_amount, ai_confidence,
               created_at, confirmed_at, confirmed_by
        FROM receipt_imports
        ORDER BY created_at DESC
        LIMIT 50
    """)).fetchall()

    return [{
        "id": r[0],
        "file_name": r[1],
        "uploaded_by": r[2],
        "supplier_name": r[3],
        "invoice_number": r[4],
        "invoice_date": r[5].isoformat() if r[5] else None,
        "processing_status": r[6],
        "subtotal": float(r[7] or 0),
        "gst_amount": float(r[8] or 0),
        "total_amount": float(r[9] or 0),
        "ai_confidence": float(r[10] or 0),
        "created_at": r[11].isoformat() if r[11] else None,
        "confirmed_at": r[12].isoformat() if r[12] else None,
        "confirmed_by": r[13],
    } for r in rows]


@router.get("/{import_id}")
def get_receipt_import_detail(
    import_id: int,
    user: User = Depends(require_receipt_ai),
    local_db: Session = Depends(get_local_db)
):
    """Retrieve detailed receipt extraction with line items and confidence scores for human verification."""
    imp = local_db.execute(text("""
        SELECT id, file_name, uploaded_by, supplier_name_extracted,
               invoice_number, invoice_date, processing_status,
               subtotal, gst_amount, total_amount, ai_confidence, created_at
        FROM receipt_imports
        WHERE id = :id
    """), {"id": import_id}).fetchone()

    if not imp:
        raise HTTPException(404, "Receipt import not found")

    items = local_db.execute(text("""
        SELECT id, raw_product_name, matched_product_id, match_source,
               master_product_id, quantity, unit, mrp, purchase_price,
               gst_percentage, batch_number, expiry_date, confidence_score,
               confidence_level, review_status, barcode, serial_number
        FROM receipt_import_items
        WHERE receipt_import_id = :id
        ORDER BY id ASC
    """), {"id": import_id}).fetchall()

    return {
        "id": imp[0],
        "file_name": imp[1],
        "uploaded_by": imp[2],
        "supplier_name": imp[3],
        "invoice_number": imp[4],
        "invoice_date": imp[5].isoformat() if imp[5] else None,
        "processing_status": imp[6],
        "subtotal": float(imp[7] or 0),
        "gst_amount": float(imp[8] or 0),
        "total_amount": float(imp[9] or 0),
        "ai_confidence": float(imp[10] or 0),
        "created_at": imp[11].isoformat() if imp[11] else None,
        "items": [{
            "id": i[0],
            "raw_product_name": i[1],
            "matched_product_id": i[2],
            "match_source": i[3],
            "master_product_id": i[4],
            "quantity": float(i[5] or 1),
            "unit": i[6] or "unit",
            "mrp": float(i[7]) if i[7] is not None else None,
            "purchase_price": float(i[8] or 0),
            "gst_percentage": float(i[9] or 0),
            "batch_number": i[10],
            "expiry_date": i[11].isoformat() if i[11] else None,
            "confidence_score": float(i[12] or 0),
            "confidence_level": i[13],
            "review_status": i[14],
            "barcode": i[15],
            "serial_number": i[16],
        } for i in items]
    }


@router.post("/{import_id}/confirm")
@limiter.limit("10/minute")
def confirm_and_import(
    request: Request,
    import_id: int,
    payload: ReceiptConfirmPayload,
    user: User = Depends(require_receipt_ai),
    local_db: Session = Depends(get_local_db)
):
    """
    Human verification confirmation step!
    Executes atomic database transaction:
    - Creates or updates supplier
    - Creates or updates local inventory products
    - Creates batches
    - Records inventory transactions
    - Creates purchase record & purchase items
    - Updates receipt status to 'imported'
    - Writes audit log
    Rolls back cleanly on any failure.
    """
    result = execute_atomic_receipt_confirmation(
        import_id=import_id,
        user_email=user.email,
        confirmation_payload=payload.model_dump(),
        local_db=local_db
    )
    return result
