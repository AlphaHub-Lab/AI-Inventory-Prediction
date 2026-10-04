from datetime import date, datetime, timedelta
from io import StringIO
import csv
import re
import secrets
import uuid
from math import ceil
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, or_, text, update
from sqlalchemy.orm import Session, joinedload
from ..db import engine, get_db
from ..dependencies import get_current_user, oauth2_scheme, require_permission, require_roles
from ..models import (AuditLog, AuthSession, Business, Category, ChatbotConversation, ChatbotMessage, CheckoutItem, CheckoutTransaction, ExpiryAlert, Forecast, InventoryBatch, InventoryTransaction,
                      KnowledgeChunk, KnowledgeDocument, ModelRun, Product, PurchaseOrder, PurchaseOrderItem, ReorderRecommendation,
                      Sale, Supplier, User, UserPermission, WastePrediction)
from ..schemas import (AdminUserUpdate, BatchInput, BulkBatchInput, BusinessCreate, BusinessStatusUpdate, CategoryInput, ChatRequest, CheckoutInput, ConvertReordersInput, ForecastRequest, LoginRequest, PermissionUpdate, POItemInput, ProductInput, PurchaseOrderInput,
                       ReorderAction, SaleInput, StatusUpdate, StockAdjustment, SupplierInput, TokenResponse, UserCreate, UserRead, WeightStockAdjustment,
                       WhatIfRequest)
from ..security import create_token, hash_password, verify_password
from ..services.chatbot import answer as chatbot_answer
from ..services.forecasting import forecast_product, forecast_sum
from ..services.operations import build_reorder, refresh_operational_insights
from ..rate_limit import limiter

api = APIRouter(prefix="/api")


def audit(db: Session, user: User | None, action: str, entity: str, entity_id: int | str, payload: dict | None = None) -> None:
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity, entity_id=str(entity_id), payload=payload or {}))


def product_data(product: Product) -> dict:
    return {"id": product.id, "sku": product.sku, "name": product.name, "category_id": product.category_id, "category_name": product.category.name if product.category else None,
            "unit": product.unit, "price": float(product.price), "supplier_id": product.supplier_id, "supplier_name": product.supplier.name if product.supplier else None,
            "manufacturing_date": product.manufacturing_date, "expiry_date": product.expiry_date, "current_stock": product.current_stock, "minimum_stock": product.minimum_stock,
            "maximum_stock": product.maximum_stock, "reorder_point": product.reorder_point, "safety_stock": product.safety_stock, "lead_time_days": product.lead_time_days,
            "status": product.status, "is_weight_based": product.is_weight_based, "category_is_grocery": bool(product.category and product.category.is_grocery),
            "weight_unit": product.weight_unit or (product.category.default_weight_unit if product.category else "kg"),
            "default_weight_g": product.default_weight_g or (product.category.default_weight_g if product.category else 1000),
            "weight_increment_g": product.weight_increment_g or (product.category.weight_increment_g if product.category else 500),
            "minimum_weight_g": product.minimum_weight_g or (product.category.minimum_weight_g if product.category else 100),
            "maximum_weight_g": product.maximum_weight_g or (product.category.maximum_weight_g if product.category else 100000),
            "weight_stock_g": product.weight_stock_g, "created_at": product.created_at, "updated_at": product.updated_at}


def validate_product_weight(body: ProductInput, category: Category) -> None:
    if body.is_weight_based and not category.is_grocery:
        raise HTTPException(422, "Weight-based selling is available only for grocery categories")
    if body.is_weight_based and body.weight_stock_g is None:
        raise HTTPException(422, "Set available weight stock in grams for weight-based products")
    if not body.is_weight_based and any(value is not None for value in (body.weight_unit, body.default_weight_g, body.weight_increment_g, body.minimum_weight_g, body.maximum_weight_g, body.weight_stock_g)):
        raise HTTPException(422, "Weight settings can only be set for weight-based grocery products")
    if body.is_weight_based:
        minimum = body.minimum_weight_g or category.minimum_weight_g
        maximum = body.maximum_weight_g or category.maximum_weight_g
        default = body.default_weight_g or category.default_weight_g
        if maximum < minimum or not minimum <= default <= maximum:
            raise HTTPException(422, "Default and maximum weights must be within the configured minimum and maximum")


def sale_data(sale: Sale) -> dict:
    return {"id": sale.id, "date": sale.date, "product_id": sale.product_id, "quantity_sold": sale.quantity_sold, "unit_price": float(sale.unit_price), "discount": sale.discount,
            "promotion": sale.promotion, "holiday": sale.holiday, "channel": sale.channel, "location": sale.location, "revenue": float(sale.revenue)}


@api.post("/auth/login", response_model=TokenResponse, tags=["auth"])
@limiter.limit("15/minute")
def login(request: Request, body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    from ..config import get_settings
    session_id = secrets.token_urlsafe(32)
    db.add(AuthSession(id=session_id, user_id=user.id, expires_at=datetime.utcnow() + timedelta(days=get_settings().refresh_token_days)))
    db.commit()

    access_token = create_token(user.email, user.role, session_id)
    refresh_token = create_token(user.email, user.role, session_id, "refresh")

    # Set real-time HTTP-only cookies (zero localStorage required)
    cookie_max_age = get_settings().refresh_token_days * 86400
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=cookie_max_age,
        secure=False,
        path="/"
    )
    response.set_cookie(
        key="session_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=cookie_max_age,
        secure=False,
        path="/"
    )

    # Sync real-time session into sessions table
    try:
        client_ip = request.client.host if request.client else "127.0.0.1"
        u_agent = request.headers.get("user-agent", "Web Client")
        exp = datetime.utcnow() + timedelta(days=get_settings().refresh_token_days)
        db.execute(text("""
            INSERT INTO sessions (user_id, token, ip_address, user_agent, expires_at, is_active)
            VALUES (:uid, :tok, :ip, :ua, :exp, true)
        """), {
            "uid": user.id,
            "tok": access_token[:255],
            "ip": client_ip[:50],
            "ua": u_agent[:255],
            "exp": exp
        })
        db.commit()
    except Exception:
        # This secondary legacy `sessions` table is optional. If it is absent
        # (as on the current admin_db schema), PostgreSQL marks the transaction
        # failed; roll it back so response serialization can still load the
        # user's business relationship. The primary auth_sessions row was
        # committed above and remains the authoritative revocable session.
        db.rollback()

    return {"access_token": access_token, "refresh_token": refresh_token, "user": user}


@api.post("/auth/refresh", tags=["auth"])
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    from jose import JWTError, jwt
    from ..config import get_settings
    from ..security import ALGORITHM
    try:
        payload = jwt.decode(refresh_token, get_settings().secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh" or not payload.get("sid"):
            raise ValueError
        user = db.query(User).filter_by(email=payload.get("sub"), is_active=True).first()
        if not user:
            raise ValueError
        session = db.query(AuthSession).filter_by(id=payload["sid"], user_id=user.id, revoked_at=None).first()
        if not session or session.expires_at <= datetime.utcnow():
            raise ValueError
        session.expires_at = datetime.utcnow() + timedelta(days=get_settings().refresh_token_days)
        db.commit()
    except (JWTError, ValueError):
        raise HTTPException(401, "Invalid refresh token")
    return {"access_token": create_token(user.email, user.role, session.id), "refresh_token": create_token(user.email, user.role, session.id, "refresh"), "token_type": "bearer"}


@api.post("/auth/logout", tags=["auth"])
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="session_token", path="/")

    # Revoke session in auth_sessions and sessions table
    token = request.cookies.get("access_token") or request.cookies.get("session_token")
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()

    if token:
        try:
            from jose import jwt
            from ..config import get_settings
            from ..security import ALGORITHM
            payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
            session = db.query(AuthSession).filter_by(id=payload.get("sid")).first()
            if session:
                session.revoked_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass

        try:
            db.execute(text("UPDATE sessions SET is_active = false WHERE token = :tok"), {"tok": token[:255]})
            db.commit()
        except Exception:
            pass

    return {"message": "Logged out successfully"}


@api.get("/auth/me", response_model=UserRead, tags=["auth"])
def me(user: User = Depends(get_current_user)):
    return user


@api.get("/users", tags=["users"])
def list_users(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    if actor.role not in {"admin", "business_owner"}:
        raise HTTPException(403, "Insufficient permissions")
    users = db.query(User).options(joinedload(User.business)).order_by(User.full_name).all()
    user_ids = [u.id for u in users]
    perms = db.query(UserPermission).filter(UserPermission.user_id.in_(user_ids)).order_by(UserPermission.permission).all() if user_ids else []
    perm_map: dict = {}
    for p in perms:
        perm_map.setdefault(p.user_id, []).append(p.permission)
    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active, "business_id": u.business_id, "business_name": u.business_name,
             "permissions": perm_map.get(u.id, [])}
            for u in users]


@api.post("/users", status_code=201, tags=["users"])
def create_user(body: UserCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "admin":
        business_id = body.business_id
        business = db.get(Business, business_id) if business_id else None
        if body.role != "admin" and (not business or not business.is_active):
            raise HTTPException(422, "Choose an active business for this account")
        if body.role == "admin" and business_id is not None:
            raise HTTPException(422, "Super administrator accounts are not assigned to a business")
        if body.role == "business_owner":
            raise HTTPException(422, "Create a business and its owner through the business workspace")
    else:
        raise HTTPException(403, "Only an administrator can create user accounts")
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(409, "Email already exists")
    created = User(email=body.email, full_name=body.full_name, password_hash=hash_password(body.password), role=body.role, business_id=business_id)
    db.add(created); db.flush(); audit(db, user, "create", "user", created.id); db.commit()
    return {"id": created.id, "email": created.email, "full_name": created.full_name, "role": created.role, "is_active": created.is_active, "business_id": created.business_id, "business_name": created.business_name}


ASSOCIATE_PERMISSIONS = {
    "inventory.view", "inventory.create", "inventory.update", "sales.view", "sales.create",
    "orders.view", "orders.create", "customers.view", "suppliers.view", "reports.view",
    "reorder.view", "reorder.create", "reorder.update", "receipt.scan", "receipt.extract",
    "receipt.review", "receipt.import",
}


@api.put("/users/{user_id}/permissions", tags=["users"])
def set_associate_permissions(user_id: int, body: PermissionUpdate, db: Session = Depends(get_db), owner: User = Depends(require_roles("business_owner"))):
    target = db.query(User).filter(User.id == user_id, User.business_id == owner.business_id, User.role == "associate").first()
    if not target:
        raise HTTPException(404, "Associate not found in your business")
    requested = set(body.permissions)
    invalid = requested - ASSOCIATE_PERMISSIONS
    if invalid:
        raise HTTPException(422, f"Unsupported associate permissions: {', '.join(sorted(invalid))}")
    db.query(UserPermission).filter(UserPermission.user_id == target.id).delete(synchronize_session=False)
    db.add_all(UserPermission(user_id=target.id, permission=name, granted_by=owner.id) for name in sorted(requested))
    audit(db, owner, "permissions_update", "user", target.id, {"permissions": sorted(requested)})
    db.commit()
    return {"user_id": target.id, "permissions": sorted(requested)}


@api.put("/admin/users/{user_id}", tags=["administrator"])
def update_admin_user(user_id: int, body: AdminUserUpdate, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == actor.id and (body.role != "admin" or not body.is_active):
        raise HTTPException(409, "You cannot remove your own administrator access")
    next_business_id = None if body.role == "admin" else (body.business_id if body.business_id is not None else target.business_id)
    next_business = db.get(Business, next_business_id) if next_business_id else None
    if body.role != "admin" and (not next_business or not next_business.is_active):
        raise HTTPException(422, "Choose an active business for this account")
    if target.role == "admin" and target.is_active and (body.role != "admin" or not body.is_active):
        active_admins = db.query(User).filter_by(role="admin", is_active=True).count()
        if active_admins <= 1:
            raise HTTPException(409, "The last active administrator cannot be disabled or demoted")
    if target.role == "business_owner" and target.is_active and (body.role != "business_owner" or not body.is_active or next_business_id != target.business_id):
        other_owners = db.query(User).filter(User.business_id == target.business_id, User.role == "business_owner", User.is_active.is_(True), User.id != target.id).count()
        if other_owners == 0:
            raise HTTPException(409, "The last active business owner cannot be disabled or reassigned")
    previous = {"role": target.role, "is_active": target.is_active, "business_id": target.business_id}
    target.role = body.role
    target.is_active = body.is_active
    target.business_id = next_business_id
    audit(db, actor, "admin_update", "user", target.id, {"before": previous, "after": {"role": body.role, "is_active": body.is_active, "business_id": next_business_id}})
    db.commit()
    return {"id": target.id, "email": target.email, "full_name": target.full_name, "role": target.role, "is_active": target.is_active, "business_id": target.business_id, "business_name": target.business_name}


@api.get("/admin/overview", tags=["administrator"])
def admin_overview(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    try:
        count_sql = text("""
            SELECT 'businesses' as k, COUNT(*) as c FROM businesses
            UNION ALL SELECT 'accounts', COUNT(*) FROM users
            UNION ALL SELECT 'products', COUNT(*) FROM products
            UNION ALL SELECT 'sales', COUNT(*) FROM sales
            UNION ALL SELECT 'inventory_movements', COUNT(*) FROM inventory_transactions
            UNION ALL SELECT 'batches', COUNT(*) FROM inventory_batches
            UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers
            UNION ALL SELECT 'categories', COUNT(*) FROM categories
            UNION ALL SELECT 'purchase_orders', COUNT(*) FROM purchase_orders
            UNION ALL SELECT 'purchase_order_items', COUNT(*) FROM purchase_order_items
            UNION ALL SELECT 'forecasts', COUNT(*) FROM forecasts
            UNION ALL SELECT 'reorder_recommendations', COUNT(*) FROM reorder_recommendations
            UNION ALL SELECT 'waste_predictions', COUNT(*) FROM waste_predictions
            UNION ALL SELECT 'expiry_alerts', COUNT(*) FROM expiry_alerts
            UNION ALL SELECT 'knowledge_documents', COUNT(*) FROM knowledge_documents
            UNION ALL SELECT 'knowledge_chunks', COUNT(*) FROM knowledge_chunks
            UNION ALL SELECT 'chat_conversations', COUNT(*) FROM chatbot_conversations
            UNION ALL SELECT 'chat_messages', COUNT(*) FROM chatbot_messages
            UNION ALL SELECT 'audit_events', COUNT(*) FROM audit_logs
            UNION ALL SELECT 'model_runs', COUNT(*) FROM model_runs
        """)
        rows = db.execute(count_sql).fetchall()
        counts = {r[0]: r[1] for r in rows}
    except Exception:
        counts = {
            "businesses": db.query(Business).count(),
            "accounts": db.query(User).count(),
            "products": db.query(Product).count(),
            "sales": db.query(Sale).count(),
            "inventory_movements": db.query(InventoryTransaction).count(),
            "batches": db.query(InventoryBatch).count(),
            "suppliers": db.query(Supplier).count(),
            "categories": db.query(Category).count(),
            "purchase_orders": db.query(PurchaseOrder).count(),
            "purchase_order_items": db.query(PurchaseOrderItem).count(),
            "forecasts": db.query(Forecast).count(),
            "reorder_recommendations": db.query(ReorderRecommendation).count(),
            "waste_predictions": db.query(WastePrediction).count(),
            "expiry_alerts": db.query(ExpiryAlert).count(),
            "knowledge_documents": db.query(KnowledgeDocument).count(),
            "knowledge_chunks": db.query(KnowledgeChunk).count(),
            "chat_conversations": db.query(ChatbotConversation).count(),
            "chat_messages": db.query(ChatbotMessage).count(),
            "audit_events": db.query(AuditLog).count(),
            "model_runs": db.query(ModelRun).count(),
        }
    active_accounts = db.query(User).filter_by(is_active=True).count()
    revenue = db.query(func.coalesce(func.sum(Sale.revenue), 0)).scalar() or 0
    dialect = engine.dialect.name
    if dialect == "sqlite":
        storage_bytes = (db.execute(text("PRAGMA page_count")).scalar() or 0) * (db.execute(text("PRAGMA page_size")).scalar() or 0)
    elif dialect == "postgresql":
        storage_bytes = db.execute(text("SELECT pg_database_size(current_database())")).scalar() or 0
    else:
        storage_bytes = None
    return {"counts": counts, "active_accounts": active_accounts, "sales_revenue": float(revenue), "database_engine": dialect, "database_bytes": storage_bytes}


@api.get("/admin/dashboard", tags=["administrator"])
def admin_dashboard(
    start: date | None = None,
    end: date | None = None,
    business_id: int | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    end = end or date.today()
    start = start or (end - timedelta(days=30))
    if start > end:
        raise HTTPException(422, "Start date must be before end date")
    if business_id is not None and not db.get(Business, business_id):
        raise HTTPException(404, "Business workspace not found")

    products_query = db.query(Product).filter(Product.status == "active")
    if business_id is not None:
        products_query = products_query.filter(Product.business_id == business_id)
    if category:
        products_query = products_query.join(Category).filter(Category.name == category)
    products = products_query.all()
    product_ids = [product.id for product in products]

    sales_query = db.query(Sale).join(Product, Sale.product_id == Product.id).filter(Sale.date >= start, Sale.date <= end)
    if business_id is not None:
        sales_query = sales_query.filter(Product.business_id == business_id)
    if category:
        sales_query = sales_query.join(Category, Product.category_id == Category.id).filter(Category.name == category)
    revenue = float(sales_query.with_entities(func.coalesce(func.sum(Sale.revenue), 0)).scalar() or 0)
    trend_rows = sales_query.with_entities(Sale.date, func.sum(Sale.revenue), func.sum(Sale.quantity_sold)).group_by(Sale.date).order_by(Sale.date).all()
    category_rows = db.query(Category.name, func.sum(Sale.revenue)).join(Product, Product.category_id == Category.id).join(Sale, Sale.product_id == Product.id).filter(Sale.date >= start, Sale.date <= end)
    if business_id is not None:
        category_rows = category_rows.filter(Product.business_id == business_id)
    if category:
        category_rows = category_rows.filter(Category.name == category)
    category_rows = category_rows.group_by(Category.name).order_by(func.sum(Sale.revenue).desc()).all()

    product_scope = Product.id.in_(product_ids) if product_ids else False
    low_stock = sum(not product.is_weight_based and product.reorder_point > 0 and product.current_stock * 5 < product.reorder_point for product in products)
    expected_demand = db.query(func.coalesce(func.sum(Sale.quantity_sold), 0)).join(Product, Sale.product_id == Product.id).filter(
        Sale.date >= end - timedelta(days=27), Sale.date <= end, product_scope
    ).scalar() or 0
    expected_demand = round(float(expected_demand) / 4)
    waste_query = db.query(func.coalesce(func.sum(WastePrediction.estimated_value), 0)).filter(WastePrediction.calculated_for == date.today(), WastePrediction.product_id.in_(product_ids) if product_ids else False)
    inventory_value = sum(product.current_stock * float(product.price) for product in products)
    reorder_query = db.query(func.count(ReorderRecommendation.id)).join(Product, ReorderRecommendation.product_id == Product.id).filter(ReorderRecommendation.status == "draft", product_scope)
    accounts_query = db.query(User).filter(User.is_active.is_(True))
    if business_id is not None:
        accounts_query = accounts_query.filter(User.business_id == business_id)

    business_rows = db.query(Business).order_by(Business.name).all()
    business_product_stats = {
        business_key: (int(product_count), int(low_count))
        for business_key, product_count, low_count in db.query(
            Product.business_id,
            func.count(Product.id),
            func.coalesce(func.sum(case((Product.is_weight_based.is_(False), case((Product.reorder_point > 0, case((Product.current_stock * 5 < Product.reorder_point, 1), else_=0)), else_=0)), else_=0)), 0),
        ).filter(Product.status == "active").group_by(Product.business_id).all()
    }
    business_account_counts = dict(db.query(User.business_id, func.count(User.id)).group_by(User.business_id).all())
    branch_sales_query = db.query(
        Product.business_id, func.coalesce(func.sum(Sale.revenue), 0), func.count(Sale.id)
    ).join(Product, Sale.product_id == Product.id).filter(Sale.date >= start, Sale.date <= end)
    if category:
        branch_sales_query = branch_sales_query.join(Category, Product.category_id == Category.id).filter(Category.name == category)
    branch_sales_stats = {business_key: (float(branch_revenue or 0), int(branch_transactions))
                          for business_key, branch_revenue, branch_transactions in branch_sales_query.group_by(Product.business_id).all()}
    business_performance = []
    for business in business_rows:
        product_count, low_count = business_product_stats.get(business.id, (0, 0))
        branch_revenue, branch_transactions = branch_sales_stats.get(business.id, (0.0, 0))
        business_performance.append({
            "id": business.id, "name": business.name, "owner_email": business.owner_email,
            "is_active": business.is_active,
            "accounts": business_account_counts.get(business.id, 0),
            "products": product_count,
            "low_stock": low_count,
            "transactions": branch_transactions,
            "revenue": float(branch_revenue or 0),
        })

    return {
        "last_updated": datetime.utcnow(), "range": {"start": start, "end": end},
        "selected_business_id": business_id, "selected_category": category,
        "businesses": [{"id": b.id, "name": b.name, "is_active": b.is_active} for b in business_rows],
        "categories": [row[0] for row in db.query(Category.name).distinct().order_by(Category.name).all()],
        "business_performance": business_performance,
        "kpis": {
            "businesses": sum(1 for b in business_rows if b.is_active),
            "accounts": accounts_query.count(),
            "products": len(products), "low_stock": low_stock, "revenue": revenue,
            "recommended_orders": reorder_query.scalar() or 0, "expected_demand": expected_demand,
            "predicted_waste_value": float(waste_query.scalar() or 0), "inventory_value": inventory_value,
        },
        "sales_trend": [{"date": day, "revenue": float(amount or 0), "units": int(units or 0)} for day, amount, units in trend_rows],
        "category_sales": [{"name": name, "value": float(amount or 0)} for name, amount in category_rows],
    }


@api.get("/admin/businesses", tags=["administrator"])
def admin_businesses(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    rows = db.query(Business).order_by(Business.created_at.desc()).all()
    account_counts = dict(db.query(User.business_id, func.count(User.id)).group_by(User.business_id).all())
    product_counts = dict(db.query(Product.business_id, func.count(Product.id)).group_by(Product.business_id).all())
    sales_counts = dict(db.query(Product.business_id, func.count(Sale.id)).join(Product, Sale.product_id == Product.id).group_by(Product.business_id).all())
    return [{
        "id": business.id, "name": business.name, "business_type": business.business_type,
        "master_database_name": business.master_database_name, "local_database_name": business.local_database_name,
        "owner_email": business.owner_email,
        "is_active": business.is_active, "created_at": business.created_at,
        "accounts": account_counts.get(business.id, 0),
        "products": product_counts.get(business.id, 0),
        "sales": sales_counts.get(business.id, 0),
    } for business in rows]


@api.post("/admin/businesses", status_code=201, tags=["administrator"])
def create_business(body: BusinessCreate, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))):
    if db.query(User).filter_by(email=body.owner_email).first():
        raise HTTPException(409, "An account with this owner email already exists")
    business_type = body.business_type
    business = Business(
        name=body.name.strip(), owner_email=body.owner_email, business_type=business_type,
        master_database_name=f"master_{business_type}", is_active=True,
    )
    db.add(business)
    db.flush()
    business.local_database_name = f"local_business_{business.id}"
    owner = User(email=body.owner_email, full_name=body.owner_name.strip(), password_hash=hash_password(body.owner_password), role="business_owner", business_id=business.id)
    db.add(owner)
    db.add(Category(name="General", is_grocery=business_type == "grocery", business_id=business.id))
    db.add(Supplier(name="Default Supplier", email=body.owner_email, business_id=business.id))
    db.flush()
    audit(db, actor, "create", "business", business.id, {"name": business.name, "business_type": business.business_type, "master_database_name": business.master_database_name, "local_database_name": business.local_database_name, "owner_email": business.owner_email})
    db.commit()
    return {"id": business.id, "name": business.name, "business_type": business.business_type, "master_database_name": business.master_database_name, "local_database_name": business.local_database_name, "owner_email": business.owner_email, "is_active": business.is_active, "created_at": business.created_at, "accounts": 1, "products": 0, "sales": 0}


@api.put("/admin/businesses/{business_id}", tags=["administrator"])
def update_business_status(business_id: int, body: BusinessStatusUpdate, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))):
    business = db.get(Business, business_id)
    if not business:
        raise HTTPException(404, "Business not found")
    business.is_active = body.is_active
    if body.business_type:
        business.business_type = body.business_type
        business.master_database_name = f"master_{body.business_type}"
    audit(db, actor, "business_status", "business", business.id, {"is_active": body.is_active, "business_type": business.business_type, "master_database_name": business.master_database_name})
    db.commit()
    return {"id": business.id, "name": business.name, "business_type": business.business_type, "master_database_name": business.master_database_name, "local_database_name": business.local_database_name, "owner_email": business.owner_email, "is_active": business.is_active}


@api.get("/admin/notifications", tags=["administrator"])
def admin_notifications(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    alerts = []
    cutoff = date.today() + timedelta(days=7)
    for business in db.query(Business).order_by(Business.name).all():
        low_stock = db.query(Product).filter(Product.business_id == business.id, Product.status == "active", Product.is_weight_based.is_(False), Product.reorder_point > 0, Product.current_stock * 5 < Product.reorder_point).count()
        expiring = db.query(Product).filter(Product.business_id == business.id, Product.expiry_date.is_not(None), Product.expiry_date <= cutoff).count()
        open_orders = db.query(PurchaseOrder).filter(PurchaseOrder.business_id == business.id, PurchaseOrder.status.in_(["draft", "approved", "ordered"])).count()
        if not business.is_active:
            alerts.append({"id": f"business-{business.id}", "severity": "critical", "business_id": business.id, "business_name": business.name, "kind": "Workspace disabled", "count": 1})
        if low_stock:
            alerts.append({"id": f"stock-{business.id}", "severity": "warning", "business_id": business.id, "business_name": business.name, "kind": "Low-stock products", "count": low_stock})
        if expiring:
            alerts.append({"id": f"expiry-{business.id}", "severity": "warning", "business_id": business.id, "business_name": business.name, "kind": "Products expiring within 7 days", "count": expiring})
        if open_orders:
            alerts.append({"id": f"orders-{business.id}", "severity": "info", "business_id": business.id, "business_name": business.name, "kind": "Open purchase orders", "count": open_orders})
    return alerts


@api.get("/admin/accounts", tags=["administrator"])
def admin_accounts(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    def grouped_counts(column):
        return dict(db.query(column, func.count()).group_by(column).all())
    audit_counts = grouped_counts(AuditLog.user_id)
    movement_counts = grouped_counts(InventoryTransaction.user_id)
    conversation_counts = grouped_counts(ChatbotConversation.user_id)
    order_counts = grouped_counts(PurchaseOrder.created_by)
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [{
        "id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role,
        "business_id": user.business_id, "business_name": user.business_name,
        "is_active": user.is_active, "created_at": user.created_at,
        "audit_events": audit_counts.get(user.id, 0),
        "inventory_movements": movement_counts.get(user.id, 0),
        "chat_conversations": conversation_counts.get(user.id, 0),
        "purchase_orders": order_counts.get(user.id, 0),
    } for user in users]


@api.delete("/admin/accounts/{user_id}", tags=["administrator"])
def delete_admin_account(user_id: int, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))):
    """Permanently remove an account and its personal authentication/assistant data."""
    target = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not target:
        raise HTTPException(404, "Account not found")
    if target.id == actor.id:
        raise HTTPException(400, "You cannot delete your own administrator account")
    if target.role == "admin" and target.is_active:
        active_admins = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
        if active_admins <= 1:
            raise HTTPException(409, "The last active administrator cannot be deleted")

    from sqlalchemy import Integer, inspect as sa_inspect
    from ..database_manager import get_local_session

    # Local operational records are shared workspace history. Detach the account
    # identity from those records while retaining products, orders, receipts, and audit history.
    local_sessions: list[Session] = []
    local_names = {name for (name,) in db.query(Business.local_database_name).filter(Business.local_database_name.is_not(None)).all() if name}
    # Legacy single-database deployments route every tenant session to the
    # configured database; scan it once to avoid duplicate concurrent updates.
    if engine.url.database in {"postgres", "inventory_system"} and local_names:
        local_names = {engine.url.database}
    local_refs = {
        "audit_logs": ("user_id",),
        "purchase_orders": ("created_by",),
        "receipt_imports": ("uploaded_by", "confirmed_by"),
        "receipt_import_items": ("edited_by",),
    }

    def anonymize(value):
        if isinstance(value, dict):
            return {key: anonymize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [anonymize(item) for item in value]
        if isinstance(value, str) and value.casefold() in {target.email.casefold(), target.full_name.casefold()}:
            return "[deleted account]"
        return value

    try:
        for database_name in sorted(local_names):
            local_db = get_local_session(database_name)
            local_sessions.append(local_db)
            inspector = sa_inspect(local_db.get_bind())
            for table_name, candidates in local_refs.items():
                if not inspector.has_table(table_name):
                    continue
                columns = {column["name"]: column for column in inspector.get_columns(table_name)}
                if table_name == "audit_logs" and "metadata" in columns:
                    for log_id, details in local_db.execute(text('SELECT id, "metadata" FROM audit_logs')).all():
                        cleaned = anonymize(details)
                        if cleaned != details:
                            local_db.execute(text('UPDATE audit_logs SET "metadata" = :details WHERE id = :log_id'), {"details": cleaned, "log_id": log_id})
                for column_name in candidates:
                    column = columns.get(column_name)
                    if not column or not column.get("nullable", True):
                        continue
                    # Validate identifiers strictly against safe identifier regex to guarantee SQL safety
                    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name) or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", column_name):
                        continue
                    if isinstance(column["type"], Integer):
                        predicate = f'"{column_name}" = :user_id'
                        params = {"user_id": target.id}
                    else:
                        predicate = f'"{column_name}" IN (:user_id_text, :email)'
                        params = {"user_id_text": str(target.id), "email": target.email}
                    local_db.execute(text(f'UPDATE "{table_name}" SET "{column_name}" = NULL WHERE {predicate}'), params)

        # Preserve permission grants and operational audit trails, but remove the
        # deleted user's own permissions, sessions, stock actor links, and chats.
        conversation_ids = [row[0] for row in db.query(ChatbotConversation.id).filter(ChatbotConversation.user_id == target.id).all()]
        if conversation_ids:
            db.query(ChatbotMessage).filter(ChatbotMessage.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
            db.query(ChatbotConversation).filter(ChatbotConversation.id.in_(conversation_ids)).delete(synchronize_session=False)
        db.query(AuthSession).filter(AuthSession.user_id == target.id).delete(synchronize_session=False)
        db.query(UserPermission).filter(UserPermission.user_id == target.id).delete(synchronize_session=False)
        db.query(UserPermission).filter(UserPermission.granted_by == target.id).update({UserPermission.granted_by: None}, synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.user_id == target.id).update({AuditLog.user_id: None}, synchronize_session=False)
        db.query(InventoryTransaction).filter(InventoryTransaction.user_id == target.id).update({InventoryTransaction.user_id: None}, synchronize_session=False)
        db.query(PurchaseOrder).filter(PurchaseOrder.created_by == target.id).update({PurchaseOrder.created_by: None}, synchronize_session=False)

        # Historical activity is kept for accountability, with the account's
        # identity removed from both its actor link and matching payload values.
        for event in db.query(AuditLog).all():
            if event.payload:
                event.payload = anonymize(event.payload)

        # Business workspaces survive account deletion; remove the deleted owner's
        # contact address from the workspace metadata.
        owned_businesses = db.query(Business).filter(func.lower(Business.owner_email) == target.email.lower()).all()
        for business in owned_businesses:
            business.owner_email = f"deleted-owner-{business.id}@deleted.invalid"

        audit(db, actor, "delete", "user", target.id, {"deleted_user_id": target.id})
        db.delete(target)
        for local_db in local_sessions:
            local_db.commit()
        db.commit()
    except HTTPException:
        db.rollback()
        for local_db in local_sessions:
            local_db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        for local_db in local_sessions:
            local_db.rollback()
        raise HTTPException(503, "Could not safely remove this account from all registered databases") from exc
    finally:
        for local_db in local_sessions:
            local_db.close()
    return {"ok": True, "deleted_user_id": user_id}


@api.get("/admin/activity", tags=["administrator"])
def admin_activity(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    rows = db.query(AuditLog, User.full_name, User.email).outerjoin(User, AuditLog.user_id == User.id).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{
        "id": event.id, "actor": full_name or "System", "actor_email": email or "",
        "action": event.action, "entity": event.entity, "entity_id": event.entity_id,
        "details": event.payload or {}, "created_at": event.created_at,
    } for event, full_name, email in rows]


@api.get("/categories", tags=["catalog"])
def list_categories(db: Session = Depends(get_db), _: User = Depends(require_permission("inventory.view"))):
    return [{"id": c.id, "name": c.name, "is_grocery": c.is_grocery, "default_weight_unit": c.default_weight_unit,
             "default_weight_g": c.default_weight_g, "weight_increment_g": c.weight_increment_g,
             "minimum_weight_g": c.minimum_weight_g, "maximum_weight_g": c.maximum_weight_g}
            for c in db.query(Category).order_by(Category.name)]


@api.post("/categories", status_code=201, tags=["catalog"])
def create_category(body: CategoryInput, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "business_owner"))):
    if db.query(Category).filter(func.lower(Category.name) == body.name.lower()).first():
        raise HTTPException(409, "Category already exists")
    category = Category(**body.model_dump()); db.add(category); db.flush(); audit(db, user, "create", "category", category.id); db.commit()
    return {"id": category.id, "name": category.name, **body.model_dump()}


@api.put("/categories/{category_id}", tags=["catalog"])
def update_category(category_id: int, body: CategoryInput, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "business_owner"))):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    duplicate = db.query(Category).filter(func.lower(Category.name) == body.name.lower(), Category.id != category_id).first()
    if duplicate:
        raise HTTPException(409, "Category already exists")
    for field, value in body.model_dump().items():
        setattr(category, field, value)
    audit(db, user, "update", "category", category.id); db.commit()
    return {"id": category.id, **body.model_dump()}


@api.get("/suppliers", tags=["suppliers"])
def list_suppliers(db: Session = Depends(get_db), _: User = Depends(require_permission("suppliers.view"))):
    return [{"id": s.id, "name": s.name, "email": s.email, "phone": s.phone, "lead_time_days": s.lead_time_days, "minimum_order_quantity": s.minimum_order_quantity, "reliability_score": s.reliability_score,
             "product_count": len(s.products)} for s in db.query(Supplier).order_by(Supplier.name)]


@api.post("/suppliers", status_code=201, tags=["suppliers"])
def create_supplier(body: SupplierInput, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "business_owner"))):
    supplier = Supplier(**body.model_dump()); db.add(supplier); db.flush(); audit(db, user, "create", "supplier", supplier.id); db.commit()
    return {"id": supplier.id, **body.model_dump()}


@api.put("/suppliers/{supplier_id}", tags=["suppliers"])
def update_supplier(supplier_id: int, body: SupplierInput, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "business_owner"))):
    supplier = db.get(Supplier, supplier_id)
    if not supplier: raise HTTPException(404, "Supplier not found")
    for field, value in body.model_dump().items(): setattr(supplier, field, value)
    audit(db, user, "update", "supplier", supplier.id); db.commit(); return {"id": supplier.id, **body.model_dump()}


@api.get("/products", tags=["products"])
def list_products(q: str | None = None, category_id: int | None = None, low_stock: bool = False, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(require_permission("inventory.view"))):
    query = db.query(Product).options(joinedload(Product.category), joinedload(Product.supplier))
    if q: query = query.filter(or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%")))
    if category_id: query = query.filter(Product.category_id == category_id)
    if low_stock: query = query.filter(Product.is_weight_based.is_(False), Product.reorder_point > 0, Product.current_stock * 5 < Product.reorder_point)
    total = query.count(); rows = query.order_by(Product.name).offset((page-1)*page_size).limit(page_size).all()
    return {"items": [product_data(p) for p in rows], "total": total, "page": page, "page_size": page_size}


@api.post("/products", status_code=201, tags=["products"])
def create_product(body: ProductInput, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.create"))):
    category = db.get(Category, body.category_id)
    if not category or not db.get(Supplier, body.supplier_id): raise HTTPException(422, "Category or supplier does not exist")
    validate_product_weight(body, category)
    business_id = user.business_id
    # Serialize sequence allocation per business. The existing composite
    # unique constraint remains the final guard against duplicate SKUs.
    if business_id is not None:
        db.query(Business).filter(Business.id == business_id).with_for_update().first()
    existing_skus = db.query(Product.sku).filter(Product.business_id == business_id).all()
    serials = [int(match.group(1)) for (sku,) in existing_skus if sku and (match := re.fullmatch(r"SKU-(\d+)", sku, re.IGNORECASE))]
    sku = f"SKU-{max(serials, default=0) + 1:04d}"
    item = Product(**{**body.model_dump(exclude={"sku"}), "sku": sku}); db.add(item); db.flush(); audit(db, user, "create", "product", item.id); db.commit(); db.refresh(item); return product_data(item)


@api.get("/products/{product_id}", tags=["products"])
def get_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("inventory.view"))):
    product = db.get(Product, product_id)
    if not product: raise HTTPException(404, "Product not found")
    payload = product_data(product)
    payload["batches"] = [{"id": b.id, "lot_number": b.lot_number, "quantity": b.quantity, "received_date": b.received_date, "expiry_date": b.expiry_date} for b in product.batches]
    return payload


@api.put("/products/{product_id}", tags=["products"])
def update_product(product_id: int, body: ProductInput, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.update"))):
    product = db.get(Product, product_id)
    if not product: raise HTTPException(404, "Product not found")
    category = db.get(Category, body.category_id)
    if not category: raise HTTPException(422, "Category does not exist")
    validate_product_weight(body, category)
    for field, value in body.model_dump(exclude={"sku"}).items(): setattr(product, field, value)
    audit(db, user, "update", "product", product.id); db.commit(); db.refresh(product); return product_data(product)


@api.delete("/products/{product_id}", status_code=204, tags=["products"])
def archive_product(product_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    product = db.get(Product, product_id)
    if not product: raise HTTPException(404, "Product not found")
    product.status = "archived"; audit(db, user, "archive", "product", product.id); db.commit()


@api.post("/inventory/{product_id}/adjust", tags=["inventory"])
def adjust_stock(product_id: int, body: StockAdjustment, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.update"))):
    product = db.get(Product, product_id)
    if not product: raise HTTPException(404, "Product not found")
    if product.current_stock + body.quantity_delta < 0: raise HTTPException(422, "Adjustment would produce negative stock")
    product.current_stock += body.quantity_delta
    if body.transaction_type == "receipt" and body.quantity_delta > 0:
        product.reorder_point += body.quantity_delta
    tx = InventoryTransaction(product_id=product_id, quantity_delta=body.quantity_delta, transaction_type=body.transaction_type, note=body.note, user_id=user.id)
    db.add(tx); audit(db, user, "stock_adjustment", "product", product.id, {"delta": body.quantity_delta, "type": body.transaction_type}); db.commit()
    return {"product_id": product_id, "current_stock": product.current_stock, "transaction_id": tx.id}


@api.post("/inventory/{product_id}/weight-adjust", tags=["inventory"])
def adjust_weight_stock(product_id: int, body: WeightStockAdjustment, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.update"))):
    product = db.get(Product, product_id)
    if not product: raise HTTPException(404, "Product not found")
    if not product.category or not product.category.is_grocery or not product.is_weight_based:
        raise HTTPException(422, "Weight stock adjustments are only available for weight-based grocery products")
    new_balance = (product.weight_stock_g or 0) + body.weight_delta_g
    if new_balance < 0: raise HTTPException(422, "Adjustment would produce negative weight stock")
    product.weight_stock_g = new_balance
    tx = InventoryTransaction(product_id=product_id, quantity_delta=0, weight_delta_g=body.weight_delta_g,
                              transaction_type=body.transaction_type, note=body.note, user_id=user.id)
    db.add(tx); audit(db, user, "weight_stock_adjustment", "product", product.id,
                      {"weight_delta_g": body.weight_delta_g, "type": body.transaction_type}); db.commit()
    return {"product_id": product_id, "weight_stock_g": product.weight_stock_g, "transaction_id": tx.id}


@api.get("/inventory/transactions", tags=["inventory"])
def list_transactions(product_id: int | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), _: User = Depends(require_permission("inventory.view"))):
    query = db.query(InventoryTransaction)
    if product_id: query = query.filter_by(product_id=product_id)
    return [{"id": t.id, "product_id": t.product_id, "quantity_delta": t.quantity_delta, "weight_delta_g": t.weight_delta_g, "transaction_type": t.transaction_type, "note": t.note, "created_at": t.created_at} for t in query.order_by(InventoryTransaction.created_at.desc()).limit(limit)]


@api.post("/inventory/batches", status_code=201, tags=["inventory"])
def receive_batches(body: BulkBatchInput | BatchInput, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.create"))):
    items = body.batches if isinstance(body, BulkBatchInput) else [body]
    results = []
    for b in items:
        product = db.get(Product, b.product_id)
        if not product:
            raise HTTPException(404, f"Product {b.product_id} not found")
        batch = InventoryBatch(
            product_id=product.id,
            lot_number=b.lot_number,
            quantity=b.quantity,
            received_date=b.received_date,
            expiry_date=b.expiry_date
        )
        db.add(batch)
        product.current_stock += b.quantity
        product.reorder_point += b.quantity
        if b.expiry_date and (not product.expiry_date or b.expiry_date < product.expiry_date):
            product.expiry_date = b.expiry_date
        tx = InventoryTransaction(
            product_id=product.id,
            quantity_delta=b.quantity,
            transaction_type="receipt",
            note=f"Batch receipt lot {b.lot_number}",
            user_id=user.id
        )
        db.add(tx)
        db.flush()
        audit(db, user, "batch_received", "product", product.id, {"lot": b.lot_number, "quantity": b.quantity, "batch_id": batch.id})
        results.append({
            "id": batch.id,
            "product_id": product.id,
            "product_name": product.name,
            "lot_number": batch.lot_number,
            "quantity": batch.quantity,
            "received_date": batch.received_date,
            "expiry_date": batch.expiry_date,
            "current_stock": product.current_stock
        })
    db.commit()
    return results if isinstance(body, BulkBatchInput) else results[0]


@api.get("/inventory/batches", tags=["inventory"])
def list_batches(product_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission("inventory.view"))):
    query = db.query(InventoryBatch)
    if product_id:
        query = query.filter_by(product_id=product_id)
    batches = query.order_by(InventoryBatch.expiry_date.asc().nullslast()).all()
    today = date.today()
    return [{
        "id": b.id,
        "product_id": b.product_id,
        "product_name": db.get(Product, b.product_id).name if db.get(Product, b.product_id) else "Unknown",
        "lot_number": b.lot_number,
        "quantity": b.quantity,
        "received_date": b.received_date,
        "expiry_date": b.expiry_date,
        "days_remaining": (b.expiry_date - today).days if b.expiry_date else None,
        "status": "expired" if (b.expiry_date and b.expiry_date < today) else ("expiring" if (b.expiry_date and (b.expiry_date - today).days <= 7) else "good")
    } for b in batches]


@api.get("/checkout/products", tags=["checkout"])
def checkout_products(q: str = Query(default="", max_length=120), db: Session = Depends(get_db), _: User = Depends(require_permission("inventory.view"))):
    query = db.query(Product).filter(Product.status == "active")
    term = q.strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    products = query.order_by(Product.name).limit(20).all()
    return [{"id": p.id, "name": p.name, "sku": p.sku, "price": float(p.price), "stock": p.current_stock,
             "expiry_date": p.expiry_date, "batch_number": None, "category_is_grocery": bool(p.category and p.category.is_grocery),
             "is_weight_based": bool(p.category and p.category.is_grocery and p.is_weight_based),
             "weight_unit": p.weight_unit or (p.category.default_weight_unit if p.category else "kg"),
             "default_weight_g": p.default_weight_g or (p.category.default_weight_g if p.category else 1000),
             "weight_increment_g": p.weight_increment_g or (p.category.weight_increment_g if p.category else 500),
             "minimum_weight_g": p.minimum_weight_g or (p.category.minimum_weight_g if p.category else 100),
             "maximum_weight_g": p.maximum_weight_g or (p.category.maximum_weight_g if p.category else 100000),
             "weight_stock_g": p.weight_stock_g} for p in products]


def checkout_data(transaction: CheckoutTransaction) -> dict:
    return {"invoice_id": transaction.invoice_id,
            "customer": {"name": transaction.customer_name, "phone": transaction.customer_phone, "customer_id": transaction.customer_id},
            "items": [{"product_id": i.product_id, "name": i.product_name, "quantity": i.quantity,
                       "unit_price": float(i.unit_price), "total": float(i.line_total), "selected_weight_g": i.selected_weight_g,
                       "weight_unit": i.weight_unit} for i in transaction.items],
            "subtotal": float(transaction.subtotal), "discount": float(transaction.discount), "tax": float(transaction.tax),
            "total": float(transaction.total), "payment_method": transaction.payment_method,
            "payment_status": transaction.payment_status, "created_at": transaction.created_at}


@api.post("/checkout/sales", status_code=201, tags=["checkout"])
def complete_checkout(body: CheckoutInput, db: Session = Depends(get_db), user: User = Depends(require_permission("sales.create"))):
    quantities: dict[int, int] = {}
    selected_weights: dict[int, int] = {}
    selected_units: dict[int, str] = {}
    for item in body.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
        if item.selected_weight_g is not None:
            if item.quantity != 1:
                raise HTTPException(422, "Weighted cart lines use a single line quantity; set the selected weight instead")
            selected_weights[item.product_id] = selected_weights.get(item.product_id, 0) + item.selected_weight_g
            selected_units[item.product_id] = item.weight_unit or "kg"
    try:
        products = {}
        for product_id in sorted(quantities):
            product = db.get(Product, product_id)
            if not product or product.status != "active":
                raise HTTPException(422, f"Product {product_id} is unavailable")
            weighted = bool(product.category and product.category.is_grocery and product.is_weight_based)
            if weighted:
                if product_id not in selected_weights or quantities[product_id] != 1:
                    raise HTTPException(422, f"Select a weight for {product.name}")
                weight_g = selected_weights[product_id]
                minimum = product.minimum_weight_g or product.category.minimum_weight_g
                maximum = product.maximum_weight_g or product.category.maximum_weight_g
                if weight_g < minimum:
                    raise HTTPException(422, f"{product.name} must be sold in at least {minimum} g")
                if weight_g > maximum:
                    raise HTTPException(422, f"{product.name} exceeds the maximum sale weight of {maximum} g")
                if product.weight_stock_g is None or product.weight_stock_g < weight_g:
                    available_g = product.weight_stock_g or 0
                    raise HTTPException(422, f"Insufficient weight stock for {product.name}. Available: {available_g} g; requested: {weight_g} g")
            else:
                if product_id in selected_weights:
                    raise HTTPException(422, "Weight selection is allowed only for configured grocery products")
                if product.current_stock <= 0:
                    raise HTTPException(422, f"{product.name} is out of stock")
                if quantities[product_id] > product.current_stock:
                    raise HTTPException(422, f"Insufficient stock for {product.name}. Available: {product.current_stock}; requested: {quantities[product_id]}")
            if product.expiry_date and product.expiry_date < date.today():
                raise HTTPException(422, f"{product.name} is expired and cannot be sold")
            products[product_id] = product

        line_totals: dict[int, Decimal] = {}
        for product_id, quantity in quantities.items():
            product = products[product_id]
            if product_id in selected_weights:
                raw = Decimal(str(product.price)) * Decimal(selected_weights[product_id]) / Decimal(1000)
            else:
                raw = Decimal(str(product.price)) * quantity
            line_totals[product_id] = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal_decimal = sum(line_totals.values(), Decimal("0.00"))
        discount_decimal = Decimal(str(body.discount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax_decimal = Decimal(str(body.tax)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if discount_decimal > subtotal_decimal:
            raise HTTPException(422, "Discount cannot exceed the subtotal")
        total_decimal = subtotal_decimal - discount_decimal + tax_decimal
        if total_decimal < 0:
            raise HTTPException(422, "Total cannot be negative")
        total = float(total_decimal)
        if body.payment_method == "cash" and (body.amount_received is None or body.amount_received < total):
            raise HTTPException(422, "Cash received must cover the total")

        for product_id, quantity in sorted(quantities.items()):
            product = products[product_id]
            weighted = product_id in selected_weights
            if weighted:
                weight_g = selected_weights[product_id]
                result = db.execute(update(Product).where(Product.id == product_id, Product.weight_stock_g >= weight_g,
                                  Product.status == "active", Product.category_id.in_(db.query(Category.id).filter(Category.is_grocery.is_(True))), Product.is_weight_based.is_(True),
                                  or_(Product.expiry_date.is_(None), Product.expiry_date >= date.today()))
                                  .values(weight_stock_g=Product.weight_stock_g - weight_g).execution_options(synchronize_session=False))
            else:
                result = db.execute(update(Product).where(Product.id == product_id, Product.current_stock >= quantity,
                                  Product.status == "active", or_(Product.expiry_date.is_(None), Product.expiry_date >= date.today()))
                                  .values(current_stock=Product.current_stock - quantity).execution_options(synchronize_session=False))
            if result.rowcount != 1:
                raise HTTPException(409, f"Stock changed while completing checkout for {products[product_id].name}. Refresh and try again.")

        transaction = CheckoutTransaction(invoice_id=f"PENDING-{uuid.uuid4().hex}", customer_name=body.customer_name.strip() or "Walk-in Customer",
                    customer_phone=body.customer_phone, customer_id=body.customer_id, subtotal=float(subtotal_decimal),
                    discount=float(discount_decimal), tax=float(tax_decimal), total=total, payment_method=body.payment_method, payment_status="PAID")
        db.add(transaction)
        db.flush()
        transaction.invoice_id = f"INV-{datetime.utcnow():%Y%m%d}-{transaction.id:03d}"
        for product_id, quantity in quantities.items():
            product = products[product_id]
            line_total = float(line_totals[product_id])
            weighted = product_id in selected_weights
            sale_quantity = 1 if weighted else quantity
            discount_ratio = float(discount_decimal / subtotal_decimal) if subtotal_decimal else 0
            db.add(CheckoutItem(transaction_id=transaction.id, product_id=product_id, product_name=product.name,
                                quantity=sale_quantity, unit_price=product.price, line_total=line_total,
                                selected_weight_g=selected_weights.get(product_id), weight_unit=selected_units.get(product_id)))
            db.add(Sale(date=date.today(), product_id=product_id, quantity_sold=sale_quantity, unit_price=product.price,
                        discount=discount_ratio, revenue=round(line_total * (1 - discount_ratio), 2),
                        channel="store", location="Main Store"))
            db.add(InventoryTransaction(product_id=product_id, quantity_delta=0 if weighted else -quantity,
                                        weight_delta_g=-selected_weights[product_id] if weighted else None, transaction_type="sale",
                                        note=(f"Invoice {transaction.invoice_id} · {selected_weights[product_id]} g" if weighted else f"Invoice {transaction.invoice_id}"), user_id=user.id))
        audit(db, user, "create", "checkout", transaction.invoice_id, {"total": total, "items": len(quantities)})
        db.commit()
        db.refresh(transaction)
        return checkout_data(transaction)
    except Exception:
        db.rollback()
        raise


@api.get("/checkout/invoices/{invoice_id}", tags=["checkout"])
def get_checkout_invoice(invoice_id: str, db: Session = Depends(get_db), _: User = Depends(require_permission("sales.view"))):
    transaction = db.query(CheckoutTransaction).filter_by(invoice_id=invoice_id).first()
    if not transaction:
        raise HTTPException(404, "Invoice not found")
    return checkout_data(transaction)


@api.get("/sales", tags=["sales"])
def list_sales(product_id: int | None = None, start: date | None = None, end: date | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), _: User = Depends(require_permission("sales.view"))):
    query = db.query(Sale)
    if product_id: query = query.filter_by(product_id=product_id)
    if start: query = query.filter(Sale.date >= start)
    if end: query = query.filter(Sale.date <= end)
    total = query.count(); rows = query.order_by(Sale.date.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"items": [sale_data(s) for s in rows], "total": total, "page": page, "page_size": page_size}


@api.post("/sales", status_code=201, tags=["sales"])
def create_sale(body: SaleInput, db: Session = Depends(get_db), user: User = Depends(require_permission("sales.create"))):
    product = db.get(Product, body.product_id)
    if not product: raise HTTPException(422, "Product does not exist")
    if product.current_stock < body.quantity_sold: raise HTTPException(422, "Insufficient stock")
    sale = Sale(**body.model_dump(), revenue=round(body.quantity_sold * body.unit_price * (1-body.discount), 2)); product.current_stock -= body.quantity_sold
    db.add(sale); db.add(InventoryTransaction(product_id=product.id, quantity_delta=-body.quantity_sold, transaction_type="sale", note=f"Sale {body.date}", user_id=user.id)); audit(db, user, "create", "sale", "new")
    db.commit(); db.refresh(sale); return sale_data(sale)


@api.get("/sales/export", tags=["sales"])
def export_sales(db: Session = Depends(get_db), _: User = Depends(require_permission("sales.view"))):
    output = StringIO(); writer = csv.DictWriter(output, fieldnames=["date", "product_id", "quantity_sold", "unit_price", "discount", "promotion", "holiday", "channel", "location", "revenue"]); writer.writeheader()
    for sale in db.query(Sale).order_by(Sale.date): writer.writerow({k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in sale_data(sale).items() if k != "id"})
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sales.csv"})


@api.post("/sales/import", tags=["sales"])
async def import_sales(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_permission("sales.create"))):
    if not file.filename or not file.filename.endswith(".csv"): raise HTTPException(422, "Upload a CSV file")
    reader = csv.DictReader((await file.read()).decode("utf-8").splitlines()); inserted = 0; errors = []
    for line, row in enumerate(reader, start=2):
        try:
            product = db.get(Product, int(row["product_id"])); quantity = int(row["quantity_sold"])
            if not product: raise ValueError("Unknown product_id")
            sale = Sale(date=date.fromisoformat(row["date"]), product_id=product.id, quantity_sold=quantity, unit_price=float(row["unit_price"]), discount=float(row.get("discount", 0)), promotion=row.get("promotion", "false").lower() == "true", holiday=row.get("holiday", "false").lower() == "true", channel=row.get("channel", "store"), location=row.get("location", "Main Store"), revenue=round(quantity * float(row["unit_price"]) * (1-float(row.get("discount", 0))), 2))
            db.add(sale); inserted += 1
        except (KeyError, ValueError) as exc: errors.append({"line": line, "error": str(exc)})
    audit(db, user, "import", "sales", "csv", {"inserted": inserted, "errors": len(errors)}); db.commit(); return {"inserted": inserted, "errors": errors[:20]}


@api.post("/forecasts/generate", tags=["forecasts"])
def generate_forecasts(body: ForecastRequest, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "business_owner"))):
    products = [db.get(Product, body.product_id)] if body.product_id else db.query(Product).filter_by(status="active").all()
    if not products or not products[0]: raise HTTPException(404, "Product not found")
    generated = []
    for product in products:
        generated.extend(forecast_product(db, product, body.horizon_days))
    models = sorted({row.model_name for row in generated})
    return {"generated": len(generated), "horizon_days": body.horizon_days, "models": models}


@api.get("/forecasts", tags=["forecasts"])
def list_forecasts(product_id: int | None = None, horizon_days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db), _: User = Depends(require_permission("ai.forecast"))):
    products = [db.get(Product, product_id)] if product_id else db.query(Product).filter_by(status="active").all()
    if not products or not products[0]: raise HTTPException(404, "Product not found")
    end = date.today() + timedelta(days=horizon_days)
    rows = db.query(Forecast).filter(Forecast.forecast_date > date.today(), Forecast.forecast_date <= end)
    if product_id: rows = rows.filter(Forecast.product_id == product_id)
    return [{"id": f.id, "product_id": f.product_id, "product_name": db.get(Product, f.product_id).name, "forecast_date": f.forecast_date, "predicted_quantity": f.predicted_quantity, "model_name": f.model_name, "model_version": f.model_version, "horizon_days": f.horizon_days} for f in rows.order_by(Forecast.forecast_date).all()]


@api.get("/forecasts/{product_id}/series", tags=["forecasts"])
def forecast_series(product_id: int, history_days: int = Query(30, ge=7, le=365), db: Session = Depends(get_db), _: User = Depends(require_permission("ai.forecast"))):
    product = db.get(Product, product_id)
    if not product: raise HTTPException(404, "Product not found")
    start = date.today() - timedelta(days=history_days)
    actual = db.query(Sale.date, func.sum(Sale.quantity_sold)).filter(Sale.product_id == product_id, Sale.date >= start).group_by(Sale.date).order_by(Sale.date).all()
    forecast = db.query(Forecast).filter(Forecast.product_id == product_id, Forecast.forecast_date > date.today()).order_by(Forecast.forecast_date).all()
    return {"product": product.name, "actual": [{"date": d, "quantity": q} for d, q in actual], "forecast": [{"date": f.forecast_date, "quantity": f.predicted_quantity} for f in forecast]}


@api.post("/insights/refresh", tags=["insights"])
def refresh_insights(db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "business_owner"))):
    refresh_operational_insights(db); return {"status": "refreshed", "as_of": datetime.utcnow()}


@api.get("/dashboard", tags=["analytics"])
def dashboard(start: date | None = None, end: date | None = None, category_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission("reports.view"))):
    end = end or date.today(); start = start or (end - timedelta(days=30))
    product_query = db.query(Product).filter(Product.status == "active")
    if category_id: product_query = product_query.filter(Product.category_id == category_id)
    products = product_query.all(); ids = [p.id for p in products]
    sales_query = db.query(Sale).filter(Sale.date >= start, Sale.date <= end)
    if ids: sales_query = sales_query.filter(Sale.product_id.in_(ids))
    revenue = float(sales_query.with_entities(func.coalesce(func.sum(Sale.revenue), 0)).scalar())
    forecast_end = date.today() + timedelta(days=7)
    forecast_totals = dict(db.query(
        Forecast.product_id, func.sum(Forecast.predicted_quantity)
    ).filter(
        Forecast.product_id.in_(ids) if ids else False,
        Forecast.forecast_date > date.today(),
        Forecast.forecast_date <= forecast_end,
    ).group_by(Forecast.product_id).all())
    recent_sales = dict(db.query(
        Sale.product_id, func.sum(Sale.quantity_sold)
    ).filter(
        Sale.product_id.in_(ids) if ids else False,
        Sale.date >= date.today() - timedelta(days=28),
        Sale.date <= date.today(),
    ).group_by(Sale.product_id).all())
    expected = ceil(sum(
        float(forecast_totals[product_id]) if product_id in forecast_totals
        else float(recent_sales.get(product_id, 0) or 0) / 4
        for product_id in ids
    ))
    wastes = db.query(WastePrediction).filter(WastePrediction.calculated_for == date.today(), WastePrediction.product_id.in_(ids) if ids else False).all()
    reorders = db.query(ReorderRecommendation).filter(ReorderRecommendation.status == "draft", ReorderRecommendation.product_id.in_(ids) if ids else False).count()
    trend = db.query(Sale.date, func.sum(Sale.revenue).label("revenue"), func.sum(Sale.quantity_sold).label("units")).filter(Sale.date >= start, Sale.date <= end).group_by(Sale.date).order_by(Sale.date).all()
    by_category = db.query(Category.name, func.sum(Sale.revenue)).join(Product, Product.category_id == Category.id).join(Sale, Sale.product_id == Product.id).filter(Sale.date >= start, Sale.date <= end).group_by(Category.name).all()
    return {"last_updated": datetime.utcnow(), "range": {"start": start, "end": end}, "kpis": {"total_products": len(products), "low_stock_products": sum(not p.is_weight_based and p.reorder_point > 0 and p.current_stock * 5 < p.reorder_point for p in products), "expiring_soon_products": sum(bool(p.expiry_date and p.expiry_date <= date.today()+timedelta(days=7)) for p in products), "predicted_waste_value": round(sum(float(w.estimated_value) for w in wastes), 2), "expected_demand": expected, "recommended_orders": reorders, "revenue": round(revenue, 2), "inventory_value": round(sum(p.current_stock * float(p.price) for p in products), 2)}, "sales_trend": [{"date": d, "revenue": float(r), "units": int(u)} for d, r, u in trend], "category_sales": [{"name": n, "value": float(v)} for n, v in by_category]}


@api.get("/analytics/suppliers", tags=["analytics"])
def supplier_analytics(db: Session = Depends(get_db), _: User = Depends(require_permission("reports.view"))):
    return [{"supplier": s.name, "lead_time_days": s.lead_time_days, "reliability_score": s.reliability_score, "products": len(s.products), "open_orders": db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == s.id, PurchaseOrder.status.in_(["draft", "approved", "ordered"])).count()} for s in db.query(Supplier).all()]


@api.get("/forecasts", tags=["forecasts"])
def list_forecasts(
    horizon_days: int = Query(default=14, ge=1, le=60),
    product_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("ai.forecast"))
):
    query = db.query(Forecast)
    if product_id:
        query = query.filter(Forecast.product_id == product_id)
    if horizon_days:
        query = query.filter(Forecast.horizon_days == horizon_days)

    today = date.today()
    rows = query.filter(Forecast.forecast_date >= today).order_by(Forecast.forecast_date.asc()).limit(300).all()

    if not rows:
        rows = query.order_by(Forecast.forecast_date.desc()).limit(300).all()

    product_ids = {f.product_id for f in rows}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}

    return [
        {
            "id": f.id,
            "product_id": f.product_id,
            "product_name": products[f.product_id].name if f.product_id in products else f"Product #{f.product_id}",
            "sku": products[f.product_id].sku if f.product_id in products else "—",
            "forecast_date": f.forecast_date.isoformat() if f.forecast_date else None,
            "predicted_quantity": float(f.predicted_quantity),
            "horizon_days": f.horizon_days,
            "model_name": f.model_name,
            "model_version": f.model_version,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in rows
    ]


@api.post("/forecasts/generate", tags=["forecasts"])
@limiter.limit("10/minute")
def generate_forecasts(
    request: Request,
    body: ForecastRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "business_owner", "associate")),
    _: User = Depends(require_permission("ai.forecast"))
):
    horizon = body.horizon_days or 14
    query = db.query(Product).filter(Product.status == "active")
    if body.product_id:
        query = query.filter(Product.id == body.product_id)
    products = query.all()

    total_generated = 0
    for p in products:
        results = forecast_product(db, p, horizon_days=horizon, persist=True)
        total_generated += len(results)

    audit(db, user, "generate_forecasts", "forecasts", "batch", {"horizon_days": horizon, "products_count": len(products), "records_generated": total_generated})
    return {"generated": total_generated, "horizon_days": horizon}


@api.get("/waste", tags=["waste"])
def list_waste(risk: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission("ai.waste_analysis"))):
    query = db.query(WastePrediction).filter(WastePrediction.calculated_for == date.today())
    if risk: query = query.filter(WastePrediction.risk_level == risk.upper())
    return [{"id": w.id, "product_id": w.product_id, "product_name": db.get(Product, w.product_id).name, "risk_level": w.risk_level, "units_at_risk": w.units_at_risk, "estimated_value": float(w.estimated_value), "recommendation": w.recommendation} for w in query.order_by(WastePrediction.estimated_value.desc())]


@api.get("/expiry", tags=["expiry"])
def list_expiry(days: int = Query(7, ge=0, le=365), db: Session = Depends(get_db), _: User = Depends(require_permission("inventory.view"))):
    cutoff = date.today() + timedelta(days=days)
    rows = db.query(Product).filter(Product.expiry_date.is_not(None), Product.expiry_date <= cutoff).order_by(Product.expiry_date).all()
    return [{"product_id": p.id, "product_name": p.name, "expiry_date": p.expiry_date, "days_remaining": (p.expiry_date-date.today()).days, "status": "expired" if p.expiry_date < date.today() else "expiring", "current_stock": p.current_stock} for p in rows]


@api.get("/reorders", tags=["reorders"])
def list_reorders(status_filter: str = "draft", db: Session = Depends(get_db), _: User = Depends(require_permission("reorder.view"))):
    rows = db.query(ReorderRecommendation).filter_by(status=status_filter).order_by(ReorderRecommendation.created_at.desc()).all()
    return [{"id": r.id, "product_id": r.product_id, "product_name": db.get(Product, r.product_id).name, "current_stock": db.get(Product, r.product_id).current_stock, "reorder_point": db.get(Product, r.product_id).reorder_point, "safety_stock": db.get(Product, r.product_id).safety_stock, "lead_time_days": db.get(Product, r.product_id).lead_time_days, "forecast_demand": r.forecast_demand, "recommended_quantity": r.recommended_quantity, "explanation": r.explanation, "status": r.status} for r in rows]


@api.post("/reorders/{recommendation_id}/action", tags=["reorders"])
def act_reorder(recommendation_id: int, body: ReorderAction, db: Session = Depends(get_db), user: User = Depends(require_permission("reorder.update"))):
    row = db.get(ReorderRecommendation, recommendation_id)
    if not row: raise HTTPException(404, "Recommendation not found")
    if row.status != "draft": raise HTTPException(409, "Only draft recommendations can be actioned")
    row.status = body.status; audit(db, user, body.status, "reorder_recommendation", row.id); db.commit(); return {"id": row.id, "status": row.status}


@api.post("/what-if", tags=["analytics"])
def what_if(body: WhatIfRequest, db: Session = Depends(get_db), _: User = Depends(require_permission("ai.business_insights"))):
    product = db.get(Product, body.product_id)
    if not product: raise HTTPException(404, "Product not found")
    lead_time = body.lead_time_days if body.lead_time_days is not None else product.lead_time_days
    normal_demand = forecast_sum(db, product, max(1, lead_time))
    demand = round(normal_demand * (1 + body.demand_change_pct/100) * (1.15 if body.promotion else 1))
    order = max(0, demand + product.safety_stock - product.current_stock)
    shelf = max(0, (product.expiry_date-date.today()).days) if product.expiry_date else 365
    shelf_demand = round(forecast_sum(db, product, min(30, shelf)) * (1 + body.demand_change_pct/100))
    waste_units = max(0, product.current_stock - shelf_demand)
    return {"product": product.name, "scenario": body.model_dump(), "forecast_demand_during_lead_time": demand, "stockout_risk": "HIGH" if product.current_stock < demand else "LOW", "waste_risk": "HIGH" if product.current_stock and waste_units/product.current_stock > .5 else ("MEDIUM" if waste_units else "LOW"), "recommended_order": order, "projected_price": round(float(product.price) * (1+body.price_change_pct/100), 2)}


@api.get("/purchase-orders", tags=["purchase orders"])
def list_pos(db: Session = Depends(get_db), _: User = Depends(require_permission("orders.view"))):
    rows = db.query(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).all()
    return [{"id": po.id, "supplier_id": po.supplier_id, "supplier_name": db.get(Supplier, po.supplier_id).name, "status": po.status, "expected_delivery": po.expected_delivery, "created_at": po.created_at, "items": [{"product_id": i.product_id, "product_name": db.get(Product, i.product_id).name, "quantity": i.quantity, "unit_price": float(i.unit_price)} for i in po.items]} for po in rows]


@api.post("/purchase-orders", status_code=201, tags=["purchase orders"])
def create_po(body: PurchaseOrderInput, db: Session = Depends(get_db), user: User = Depends(require_permission("orders.create"))):
    supplier = db.get(Supplier, body.supplier_id)
    if not supplier: raise HTTPException(422, "Supplier does not exist")
    po = PurchaseOrder(supplier_id=supplier.id, expected_delivery=body.expected_delivery or date.today()+timedelta(days=supplier.lead_time_days), created_by=user.id)
    db.add(po); db.flush()
    for item in body.items:
        product = db.get(Product, item.product_id)
        if not product or product.supplier_id != supplier.id: raise HTTPException(422, "Every item must belong to the selected supplier")
        db.add(PurchaseOrderItem(purchase_order_id=po.id, **item.model_dump()))
    audit(db, user, "create", "purchase_order", po.id); db.commit(); return {"id": po.id, "status": po.status}


@api.post("/purchase-orders/from-reorders", status_code=201, tags=["purchase orders"])
def convert_reorders_to_pos(body: ConvertReordersInput, db: Session = Depends(get_db), user: User = Depends(require_permission("orders.create"))):
    recommendations = db.query(ReorderRecommendation).filter(ReorderRecommendation.id.in_(body.recommendation_ids)).all()
    if not recommendations:
        raise HTTPException(404, "No recommendations found")
    
    by_supplier: dict[int, list[tuple[ReorderRecommendation, Product]]] = {}
    for r in recommendations:
        product = db.get(Product, r.product_id)
        if not product:
            continue
        by_supplier.setdefault(product.supplier_id, []).append((r, product))
    
    created_pos = []
    for supplier_id, rec_pairs in by_supplier.items():
        supplier = db.get(Supplier, supplier_id)
        delivery = date.today() + timedelta(days=supplier.lead_time_days if supplier else 3)
        po = PurchaseOrder(supplier_id=supplier_id, expected_delivery=delivery, created_by=user.id, status="draft")
        db.add(po)
        db.flush()
        
        for r, product in rec_pairs:
            qty = max(1, r.recommended_quantity)
            db.add(PurchaseOrderItem(purchase_order_id=po.id, product_id=product.id, quantity=qty, unit_price=float(product.price)))
            r.status = "approved"  # marked as approved / converted
        
        audit(db, user, "convert_from_reorder", "purchase_order", po.id, {"items_count": len(rec_pairs)})
        created_pos.append(po.id)
    
    db.commit()
    return {"created_pos": created_pos, "message": f"Successfully created {len(created_pos)} purchase order(s)"}


@api.post("/purchase-orders/{po_id}/receive", tags=["purchase orders"])
def receive_po(po_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("orders.update"))):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po.status == "received":
        raise HTTPException(400, "Purchase order is already received")
    
    po.status = "received"
    received_items = []
    for item in po.items:
        product = db.get(Product, item.product_id)
        if product:
            lot = f"PO{po.id}-LOT{item.id}"
            product.current_stock += item.quantity
            product.reorder_point += item.quantity
            expiry = date.today() + timedelta(days=90)
            batch = InventoryBatch(product_id=product.id, lot_number=lot, quantity=item.quantity, received_date=date.today(), expiry_date=expiry)
            db.add(batch)
            db.add(InventoryTransaction(product_id=product.id, quantity_delta=item.quantity, transaction_type="receipt", note=f"PO #{po.id} receipt", user_id=user.id))
            received_items.append({"product_id": product.id, "product_name": product.name, "quantity": item.quantity, "lot_number": lot})
    
    audit(db, user, "received", "purchase_order", po.id, {"items": len(received_items)})
    db.commit()
    return {"id": po.id, "status": "received", "items_received": received_items}


@api.post("/purchase-orders/{po_id}/status", tags=["purchase orders"])
def update_po_status(po_id: int, body: StatusUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("orders.update"))):
    po = db.get(PurchaseOrder, po_id)
    if not po: raise HTTPException(404, "Purchase order not found")
    if body.status in {"approved", "ordered", "received"} and user.role not in {"admin", "business_owner"}: raise HTTPException(403, "Business owner approval required")
    if body.status == "received" and po.status != "received":
        return receive_po(po_id, db, user)
    po.status = body.status; audit(db, user, "status_change", "purchase_order", po.id, {"status": body.status}); db.commit(); return {"id": po.id, "status": po.status}


@api.get("/knowledge", tags=["knowledge"])
def list_knowledge(db: Session = Depends(get_db), _: User = Depends(require_permission("ai.rag"))):
    return [{"id": d.id, "title": d.title, "body": d.body, "created_at": d.created_at} for d in db.query(KnowledgeDocument).order_by(KnowledgeDocument.title)]


@api.post("/knowledge", status_code=201, tags=["knowledge"])
def create_knowledge(title: str, body: str, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "business_owner"))):
    document = KnowledgeDocument(title=title, body=body); db.add(document); db.flush(); db.add(KnowledgeChunk(document_id=document.id, content=body, metadata_json={"section": title})); audit(db, user, "create", "knowledge_document", document.id); db.commit(); return {"id": document.id, "title": document.title}


@api.get("/models/runs", tags=["model evaluation"])
def model_runs(db: Session = Depends(get_db), _: User = Depends(require_permission("ai.forecast"))):
    return [{"id": r.id, "model_name": r.model_name, "version": r.version, "train_start": r.train_start, "train_end": r.train_end, "mae": r.mae, "rmse": r.rmse, "mape": r.mape, "r2": r.r2, "horizon_days": r.horizon_days, "trained_at": r.created_at} for r in db.query(ModelRun).order_by(ModelRun.created_at.desc())]


@api.post("/models/train", tags=["model evaluation"])
def trigger_model_training(db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "business_owner"))):
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    train_script = root / "ml" / "train_forecasts.py"
    spec = importlib.util.spec_from_file_location("train_forecasts", str(train_script))
    if not spec or not spec.loader:
        raise HTTPException(500, "Could not load ML training module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from ..config import get_settings
    business_id = user.business_id
    if business_id is None:
        business_id = db.query(Product.business_id).filter(Product.sku.like("SKU-%")).first()
        business_id = business_id[0] if business_id else None
    if business_id is None:
        raise HTTPException(422, "No imported supermarket sales dataset is available for training")
    results = module.train(get_settings().database_url, business_id=business_id, sku_prefix="SKU-")
    audit(db, user, "train_models", "model_runs", "batch", {"models_count": len(results)})
    return {"message": "Models trained and evaluated successfully", "results": results}


@api.get("/system/info", tags=["system"])
def system_info(user: User = Depends(get_current_user)):
    from ..config import get_settings
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "database_engine": "SQLite" if "sqlite" in settings.database_url else "PostgreSQL",
        "llm_configured": bool(settings.llm_api_key),
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "rate_limiting": "20 requests/minute (SlowAPI)",
        "auth_security": "JWT RBAC with PBKDF2-SHA256 password hashing",
        "version": "1.0.0"
    }


@api.post("/chat", tags=["chatbot"])
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest, db: Session = Depends(get_db), user: User = Depends(require_permission("ai.chat"))):
    conversation = db.get(ChatbotConversation, body.conversation_id) if body.conversation_id else None
    if conversation and conversation.user_id != user.id: raise HTTPException(403, "Conversation belongs to another user")
    active_business_id = user.business_id or db.info.get("business_id")
    if not active_business_id:
        first_biz = db.query(Business.id).filter(Business.is_active.is_(True)).first()
        active_business_id = first_biz[0] if first_biz else 1
    if "business_id" not in db.info or db.info.get("business_id") is None:
        db.info["business_id"] = active_business_id
    if not conversation:
        conversation = ChatbotConversation(business_id=active_business_id, user_id=user.id, title=body.message[:80]); db.add(conversation); db.flush()
    response, intent, tool_data, citations = await chatbot_answer(db, body.message)
    db.add(ChatbotMessage(business_id=active_business_id, conversation_id=conversation.id, role="user", content=body.message, intent=intent))
    db.add(ChatbotMessage(business_id=active_business_id, conversation_id=conversation.id, role="assistant", content=response, intent=intent, citations=[{"title": c["title"], "section": c["section"]} for c in citations]))
    db.commit()
    return {"conversation_id": conversation.id, "intent": intent, "response": response, "tool_data": tool_data, "citations": [{"title": c["title"], "section": c["section"]} for c in citations]}


@api.get("/chat/conversations", tags=["chatbot"])
def conversations(db: Session = Depends(get_db), user: User = Depends(require_permission("ai.chat"))):
    return [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in db.query(ChatbotConversation).filter_by(user_id=user.id).order_by(ChatbotConversation.updated_at.desc())]


@api.get("/chat/conversations/{conversation_id}", tags=["chatbot"])
def conversation_messages(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("ai.chat"))):
    conversation = db.get(ChatbotConversation, conversation_id)
    if not conversation: raise HTTPException(404, "Conversation not found")
    if conversation.user_id != user.id: raise HTTPException(403, "Conversation belongs to another user")
    return [{"id": m.id, "role": m.role, "content": m.content, "intent": m.intent, "citations": m.citations, "created_at": m.created_at} for m in db.query(ChatbotMessage).filter_by(conversation_id=conversation_id).order_by(ChatbotMessage.created_at)]
