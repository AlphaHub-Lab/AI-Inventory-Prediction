"""
Administrator Multi-Tenant Management Router
Handles:
- Dynamic business provisioning with dedicated physical PostgreSQL local database
- Master catalog inspection across all 5 business types (medical, grocery, restaurant, stationery, dairy)
- Database registry monitoring
- Central audit logs
"""

from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database_manager import get_admin_session, get_master_session, provision_new_business_database
from ..dependencies import get_admin_db, get_current_user, require_roles
from ..models import AuditLog, Business, User
from ..security import hash_password
from ..rate_limit import limiter

_CATALOG_SUMMARY_CACHE = {"timestamp": 0.0, "data": []}
_CACHE_TTL_SECONDS = 60.0

router = APIRouter(prefix="/api/admin-system", tags=["System Administrator"])


class BusinessCreateExtended(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    business_type: str = Field(pattern="^(medical|grocery|restaurant|food|stationery|dairy|clothing|others)$")
    owner_name: str = Field(min_length=2, max_length=120)
    owner_email: EmailStr
    owner_password: str = Field(min_length=8, max_length=128)
    address: Optional[str] = None
    phone: Optional[str] = None


@router.post("/businesses", status_code=201)
@limiter.limit("5/minute")
def create_business_with_dedicated_database(
    request: Request,
    body: BusinessCreateExtended,
    user: User = Depends(require_roles("admin")),
    admin_db: Session = Depends(get_admin_db)
):
    """
    Administrator creates a new business.
    Workflow:
    Business -> Select business_type -> Select corresponding master database ->
    CREATE DEDICATED PHYSICAL LOCAL DATABASE (local_business_<id>) on PostgreSQL server ->
    Apply full 19-table schema & default supplier -> Register in database_registry ->
    Create Business Owner account.
    """
    if admin_db.query(User).filter_by(email=body.owner_email).first():
        raise HTTPException(409, "An account with this owner email already exists.")

    b_type = body.business_type.lower().strip()
    master_db_name = f"master_{b_type}"

    # 1. Insert into admin_db.businesses
    business = Business(
        name=body.name.strip(),
        owner_email=body.owner_email,
        business_type=b_type,
        master_database_name=master_db_name,
        is_active=True
    )
    admin_db.add(business)
    admin_db.flush()

    local_db_name = f"local_business_{business.id}"
    business.local_database_name = local_db_name

    # 2. Physically create and provision local database on PostgreSQL cluster
    try:
        provision_new_business_database(
            business_id=business.id,
            business_type=b_type,
            business_name=business.name,
            owner_email=business.owner_email
        )
    except Exception as e:
        admin_db.rollback()
        raise HTTPException(500, f"Failed to provision physical local database '{local_db_name}': {str(e)}")

    # 3. Create Business Owner account
    owner = User(
        email=body.owner_email,
        full_name=body.owner_name.strip(),
        password_hash=hash_password(body.owner_password),
        role="business_owner",
        business_id=business.id,
        is_active=True
    )
    admin_db.add(owner)

    # 4. Register in database_registry
    admin_db.execute(text("""
        INSERT INTO database_registry (
            database_name, database_type, business_type, business_id, status, created_at
        ) VALUES (
            :dbname, 'local', :btype, :bid, 'active', NOW()
        )
    """), {
        "dbname": local_db_name,
        "btype": b_type,
        "bid": business.id
    })

    # 5. Record central audit log
    admin_db.add(AuditLog(
        user_id=user.id,
        action="BUSINESS_CREATED",
        entity="business",
        entity_id=str(business.id),
        payload={
            "name": business.name,
            "business_type": b_type,
            "master_database": master_db_name,
            "local_database": local_db_name,
            "owner": body.owner_email
        }
    ))

    admin_db.commit()

    return {
        "message": f"Business '{business.name}' created with physical database '{local_db_name}'.",
        "id": business.id,
        "name": business.name,
        "business_type": business.business_type,
        "master_database_name": business.master_database_name,
        "local_database_name": business.local_database_name,
        "owner_email": business.owner_email,
        "is_active": business.is_active,
        "created_at": business.created_at.isoformat() if business.created_at else None
    }


@router.get("/database-registry")
def get_database_registry(
    user: User = Depends(require_roles("admin")),
    admin_db: Session = Depends(get_admin_db)
):
    """View all registered databases across the multi-tenant PostgreSQL cluster."""
    rows = admin_db.execute(text("""
        SELECT id, database_name, database_type, business_type, business_id, status, created_at
        FROM database_registry
        ORDER BY id ASC
    """)).fetchall()

    return [{
        "id": r[0],
        "database_name": r[1],
        "database_type": r[2],
        "business_type": r[3],
        "business_id": r[4],
        "status": r[5],
        "created_at": r[6].isoformat() if r[6] else None
    } for r in rows]


def _inspect_single_catalog(c: str) -> dict:
    db_name = f"master_{c}"
    m_session = None
    try:
        m_session = get_master_session(c)
        prod_count = m_session.execute(text("SELECT COUNT(*) FROM catalog.products")).fetchone()[0]
        sup_count = m_session.execute(text("SELECT COUNT(*) FROM catalog.suppliers")).fetchone()[0]
        samples = m_session.execute(text("SELECT id, sku, product_name, category FROM catalog.products LIMIT 5")).fetchall()
        return {
            "business_type": c,
            "database_name": db_name,
            "status": "online",
            "product_count": prod_count,
            "supplier_count": sup_count,
            "sample_products": [{"id": str(s[0]), "sku": s[1], "name": s[2], "category": s[3]} for s in samples]
        }
    except Exception as e:
        return {
            "business_type": c,
            "database_name": db_name,
            "status": "error",
            "error": str(e)
        }
    finally:
        if m_session:
            try:
                m_session.close()
            except Exception:
                pass


@router.get("/master-catalogs-summary")
@limiter.limit("30/minute")
def get_master_catalogs_summary(
    request: Request,
    user: User = Depends(require_roles("admin"))
):
    """Inspect product catalog sizes and status across all 5 master databases concurrently with caching."""
    now = time.time()
    if _CATALOG_SUMMARY_CACHE["data"] and (now - _CATALOG_SUMMARY_CACHE["timestamp"]) < _CACHE_TTL_SECONDS:
        return _CATALOG_SUMMARY_CACHE["data"]

    catalogs = ["medical", "grocery", "restaurant", "stationery", "dairy"]
    results = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_cat = {executor.submit(_inspect_single_catalog, c): c for c in catalogs}
        for future in as_completed(future_to_cat):
            cat = future_to_cat[future]
            try:
                results[cat] = future.result(timeout=8.0)
            except Exception as e:
                results[cat] = {
                    "business_type": cat,
                    "database_name": f"master_{cat}",
                    "status": "error",
                    "error": str(e)
                }

    ordered_summary = [results[c] for c in catalogs if c in results]
    _CATALOG_SUMMARY_CACHE["timestamp"] = now
    _CATALOG_SUMMARY_CACHE["data"] = ordered_summary
    return ordered_summary



@router.get("/audit-logs")
def get_system_audit_logs(
    limit: int = 100,
    user: User = Depends(require_roles("admin")),
    admin_db: Session = Depends(get_admin_db)
):
    """View central audit logs across all businesses."""
    logs = admin_db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{
        "id": l.id,
        "user_id": l.user_id,
        "action": l.action,
        "entity": l.entity,
        "entity_id": l.entity_id,
        "payload": l.payload,
        "created_at": l.created_at.isoformat() if l.created_at else None,
        "business_id": l.business_id
    } for l in logs]
