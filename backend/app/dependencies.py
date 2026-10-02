from collections.abc import Callable
from datetime import datetime
from typing import Generator, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from .config import get_settings
from .database_manager import get_admin_session, get_local_session, get_master_session
from .models import AuthSession, Business, User, UserPermission
from .security import ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_admin_db() -> Generator[Session, None, None]:
    """Yield a database session connected to admin_db."""
    db = get_admin_session()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    admin_db: Session = Depends(get_admin_db)
) -> User:
    """
    Authenticate user via Authorization header Bearer token OR secure session cookie.
    Validates active session in admin_db.auth_sessions.
    Attaches business context (business_id, business_type, local_database_name, master_database_name).
    """
    auth_token = token
    if not auth_token:
        auth_token = request.cookies.get("session_token") or request.cookies.get("access_token")
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in."
        )

    try:
        payload = jwt.decode(auth_token, get_settings().secret_key, algorithms=[ALGORITHM])
        email = payload.get("sub")
        session_id = payload.get("sid")
        if not email or not session_id or payload.get("type") != "access":
            raise ValueError("invalid token")
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token."
        )

    user = admin_db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or missing."
        )

    active_session = admin_db.query(AuthSession.id).filter(
        AuthSession.id == session_id,
        AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > datetime.utcnow(),
    ).first()
    if not active_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or been revoked."
        )

    # Attach dynamic database routing info to the user object
    if user.role != "admin":
        business = admin_db.get(Business, user.business_id) if user.business_id else None
        if not business or not business.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your business workspace is inactive or missing."
            )
        user.business_name_val = business.name
        user.business_type_val = business.business_type
        user.local_database_name_val = business.local_database_name or f"local_business_{business.id}"
        user.master_database_name_val = business.master_database_name or f"master_{business.business_type}"
    else:
        user.business_name_val = "System Administration"
        user.business_type_val = "all"
        user.local_database_name_val = None
        user.master_database_name_val = None

    return user


def require_roles(*roles: str) -> Callable:
    """Enforce allowed roles (Administrator, Business Owner, Associate)."""
    def check(user: User = Depends(get_current_user)) -> User:
        owner_access = user.role == "business_owner" and "business_owner" in roles
        if user.role not in roles and user.role != "admin" and not owner_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for role '{user.role}'."
            )
        return user
    return check


def require_permission(permission: str) -> Callable:
    """
    Allow administrators and owners; associates need an explicit grant.
    Associates are strictly forbidden from general AI permissions (ai.*).
    """
    def check(user: User = Depends(get_current_user), admin_db: Session = Depends(get_admin_db)) -> User:
        # Strictly block associates from all general AI endpoints
        if permission.startswith("ai.") and user.role == "associate":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="General AI capabilities are restricted to Administrators and Business Owners."
            )

        if user.role in {"admin", "business_owner"}:
            return user

        granted = admin_db.query(UserPermission.id).filter(
            UserPermission.user_id == user.id,
            UserPermission.permission == permission,
        ).first()
        if not granted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation '{permission}' is not permitted for your associate account."
            )
        return user
    return check


def require_general_ai(user: User = Depends(get_current_user)) -> User:
    """
    Strictly forbids Associates from accessing general AI capabilities:
    ai.chat, ai.forecast, ai.inventory_prediction, ai.waste_analysis, ai.business_insights, ai.recommendations, ai.rag.
    Only Administrators and Business Owners are allowed.
    """
    if user.role == "associate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="General AI capabilities (forecasting, chatbot, waste analysis) are restricted to Administrators and Business Owners."
        )
    return user


def require_receipt_ai(
    user: User = Depends(get_current_user),
    admin_db: Session = Depends(get_admin_db)
) -> User:
    """
    Allows Administrator and Business Owner.
    Allows Associate ONLY IF they have at least one receipt permission granted.
    """
    if user.role in {"admin", "business_owner"}:
        return user

    receipt_perms = ["receipt.scan", "receipt.extract", "receipt.review", "receipt.import"]
    granted = admin_db.query(UserPermission.id).filter(
        UserPermission.user_id == user.id,
        UserPermission.permission.in_(receipt_perms)
    ).first()
    if not granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Receipt AI operations are not granted to your account. Contact your Business Owner."
        )
    return user


def get_local_db(
    user: User = Depends(get_current_user),
    admin_db: Session = Depends(get_admin_db)
) -> Generator[Session, None, None]:
    """
    Yields a connection pool session to the business's dedicated local database.
    Business isolation is strictly enforced: frontend cannot supply arbitrary database or business_id.
    """
    if user.role == "admin":
        # Admin defaults to local_business_1 or can target selected business
        dbname = "local_business_1"
    else:
        dbname = getattr(user, "local_database_name_val", None) or f"local_business_{user.business_id}"

    db = get_local_session(dbname)
    try:
        yield db
    finally:
        db.close()


def get_master_db(
    user: User = Depends(get_current_user),
    admin_db: Session = Depends(get_admin_db)
) -> Generator[Session, None, None]:
    """
    Yields a connection pool session to the business's corresponding master database.
    """
    if user.role == "admin":
        b_type = "medical"
    else:
        b_type = getattr(user, "business_type_val", "grocery")

    db = get_master_session(b_type)
    try:
        yield db
    finally:
        db.close()
