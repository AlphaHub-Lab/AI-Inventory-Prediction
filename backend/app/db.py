from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from fastapi import Request
from jose import JWTError, jwt
from .config import get_settings
from .security import ALGORITHM

settings = get_settings()


def _sqlalchemy_database_url(value: str) -> str:
    """Use the installed psycopg 3 driver for standard PostgreSQL URLs."""
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql+psycopg2://"):
        return value.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    return value


engine = create_engine(_sqlalchemy_database_url(settings.database_url), pool_pre_ping=True, pool_recycle=300, pool_size=10, max_overflow=20, connect_args={"connect_timeout": 5})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db(request: Request):
    db = SessionLocal()
    try:
        # Shared-schema business tables must be filtered for the authenticated
        # tenant. The auth endpoints are excluded so a stale browser session
        # cannot prevent a user from signing into a different account.
        if not request.url.path.startswith("/api/auth/"):
            authorization = request.headers.get("authorization", "")
            token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else None
            token = token or request.cookies.get("session_token") or request.cookies.get("access_token")
            if token:
                try:
                    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
                except JWTError:
                    payload = {}
                if payload.get("type") == "access" and payload.get("sub"):
                    # Import at request time to avoid a cycle (models imports Base from this module).
                    from .models import User

                    tenant_user = db.query(User).filter(User.email == payload["sub"]).first()
                    if tenant_user:
                        if tenant_user.role == "admin":
                            db.info["super_admin"] = True
                        elif tenant_user.business_id is not None:
                            db.info["business_id"] = tenant_user.business_id
        yield db
    finally:
        db.close()
