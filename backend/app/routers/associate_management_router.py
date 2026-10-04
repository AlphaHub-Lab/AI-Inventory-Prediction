"""
Associate & Permission Management Router for Business Owners
Allows:
- Listing Associates under the current Business Owner
- Creating Associate accounts
- Assigning granular permissions (inventory.*, sales.*, orders.*, reorder.*, receipt.*)
- Strictly prohibiting granting general AI permissions to associates
- Enabling/disabling associate accounts
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..dependencies import get_admin_db, get_current_user, require_roles
from ..models import Business, User, UserPermission
from ..security import hash_password
from ..rate_limit import limiter

router = APIRouter(prefix="/api/business/associates", tags=["Associate Management"])

# Permissible operations that an owner can assign to an associate
ALLOWED_ASSOCIATE_PERMISSIONS = {
    "inventory.view", "inventory.create", "inventory.update",
    "sales.view", "sales.create",
    "orders.view", "orders.create",
    "customers.view", "suppliers.view",
    "reports.view",
    "reorder.view", "reorder.create", "reorder.update",
    "receipt.scan", "receipt.extract", "receipt.review", "receipt.import"
}

# Forbidden for associates per prompt rules
DISALLOWED_ASSOCIATE_PERMISSIONS = {
    "ai.chat", "ai.forecast", "ai.inventory_prediction",
    "ai.waste_analysis", "ai.business_insights",
    "ai.recommendations", "ai.rag"
}


class AssociateCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    permissions: List[str] = Field(default_factory=list)


class AssociatePermissionsUpdate(BaseModel):
    permissions: List[str]


class AssociateStatusUpdate(BaseModel):
    is_active: bool


@router.get("")
def list_business_associates(
    user: User = Depends(require_roles("business_owner", "admin")),
    admin_db: Session = Depends(get_admin_db)
):
    """List all associates in the owner's business with their explicit permissions."""
    b_id = user.business_id
    if user.role == "admin" and not b_id:
        associates = admin_db.query(User).filter_by(role="associate").all()
    else:
        associates = admin_db.query(User).filter_by(business_id=b_id, role="associate").all()

    results = []
    for assoc in associates:
        perms = [p.permission for p in admin_db.query(UserPermission).filter_by(user_id=assoc.id).all()]
        results.append({
            "id": assoc.id,
            "full_name": assoc.full_name,
            "email": assoc.email,
            "is_active": assoc.is_active,
            "role": assoc.role,
            "business_id": assoc.business_id,
            "created_at": assoc.created_at.isoformat() if assoc.created_at else None,
            "permissions": perms
        })
    return results


@router.post("", status_code=201)
@limiter.limit("10/minute")
def create_associate(
    request: Request,
    body: AssociateCreate,
    user: User = Depends(require_roles("business_owner", "admin")),
    admin_db: Session = Depends(get_admin_db)
):
    """
    Create an Associate account under the owner's business and grant initial permissions.
    Associates must NEVER receive general AI permissions.
    """
    # Check if email exists
    if admin_db.query(User).filter_by(email=body.email).first():
        raise HTTPException(409, "An account with this email address already exists.")

    b_id = user.business_id
    if not b_id and user.role != "admin":
        raise HTTPException(400, "Business owner account has no associated workspace.")

    # Validate permissions
    invalid_perms = [p for p in body.permissions if p in DISALLOWED_ASSOCIATE_PERMISSIONS]
    if invalid_perms:
        raise HTTPException(
            403,
            f"Associates cannot be granted general AI permissions: {', '.join(invalid_perms)}. Only receipt AI permissions can be assigned."
        )

    # Create associate user
    assoc = User(
        email=body.email,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        role="associate",
        business_id=b_id,
        is_active=True
    )
    admin_db.add(assoc)
    admin_db.flush()

    # Grant permissions
    for p in body.permissions:
        if p in ALLOWED_ASSOCIATE_PERMISSIONS:
            admin_db.add(UserPermission(
                user_id=assoc.id,
                permission=p,
                granted_by=user.id
            ))

    admin_db.commit()

    return {
        "message": f"Associate account '{assoc.full_name}' created successfully.",
        "id": assoc.id,
        "email": assoc.email,
        "permissions": body.permissions
    }


@router.put("/{associate_id}/permissions")
def update_associate_permissions(
    associate_id: int,
    body: AssociatePermissionsUpdate,
    user: User = Depends(require_roles("business_owner", "admin")),
    admin_db: Session = Depends(get_admin_db)
):
    """Update granular permissions for an associate."""
    assoc = admin_db.get(User, associate_id)
    if not assoc or assoc.role != "associate":
        raise HTTPException(404, "Associate user not found.")

    if user.role != "admin" and assoc.business_id != user.business_id:
        raise HTTPException(403, "Cannot manage associates from another business.")

    # Block general AI permissions
    blocked = [p for p in body.permissions if p in DISALLOWED_ASSOCIATE_PERMISSIONS]
    if blocked:
        raise HTTPException(
            403,
            f"Associates cannot be granted general AI permissions: {', '.join(blocked)}."
        )

    # Clear existing and add new
    admin_db.query(UserPermission).filter_by(user_id=assoc.id).delete()
    for p in body.permissions:
        if p in ALLOWED_ASSOCIATE_PERMISSIONS:
            admin_db.add(UserPermission(
                user_id=assoc.id,
                permission=p,
                granted_by=user.id
            ))

    admin_db.commit()

    return {
        "message": "Permissions updated successfully.",
        "associate_id": assoc.id,
        "permissions": body.permissions
    }


@router.put("/{associate_id}/status")
def toggle_associate_status(
    associate_id: int,
    body: AssociateStatusUpdate,
    user: User = Depends(require_roles("business_owner", "admin")),
    admin_db: Session = Depends(get_admin_db)
):
    """Enable or disable an associate account."""
    assoc = admin_db.get(User, associate_id)
    if not assoc or assoc.role != "associate":
        raise HTTPException(404, "Associate user not found.")

    if user.role != "admin" and assoc.business_id != user.business_id:
        raise HTTPException(403, "Cannot modify associates of another business.")

    assoc.is_active = body.is_active
    admin_db.commit()

    return {"message": f"Associate account {'enabled' if body.is_active else 'disabled'} successfully."}
