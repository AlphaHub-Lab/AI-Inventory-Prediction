from collections.abc import Callable
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from .config import get_settings
from .db import get_db
from .models import AuthSession, Business, User, UserPermission
from .security import ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        email = payload.get("sub")
        session_id = payload.get("sid")
        if not email or not session_id or payload.get("type") != "access":
            raise ValueError("invalid token")
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or missing")
    active_session = db.query(AuthSession.id).filter(
        AuthSession.id == session_id,
        AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > datetime.utcnow(),
    ).first()
    if not active_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is expired or revoked")
    if user.role != "admin":
        business = db.get(Business, user.business_id) if user.business_id else None
        if not business or not business.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Business workspace is inactive or missing")
        db.info["business_id"] = business.id
        db.info["super_admin"] = False
    else:
        db.info["super_admin"] = True
    return user


def require_roles(*roles: str) -> Callable:
    def check(user: User = Depends(get_current_user)) -> User:
        owner_access = user.role == "business_owner" and "business_owner" in roles
        if user.role not in roles and user.role != "admin" and not owner_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return check


def require_permission(permission: str) -> Callable:
    """Allow administrators and owners; associates need an explicit grant."""
    def check(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if user.role in {"admin", "business_owner"}:
            return user
        granted = db.query(UserPermission.id).filter(
            UserPermission.user_id == user.id,
            UserPermission.permission == permission,
        ).first()
        if not granted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action is not granted to your account")
        return user
    return check
