import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from fastapi import Request
from jose import JWTError, jwt
from .config import get_settings
from .security import ALGORITHM

logger = logging.getLogger("db")
settings = get_settings()


def _sqlalchemy_database_url(value: str) -> str:
    """Use the installed psycopg 3 driver for standard PostgreSQL URLs and enforce SSL for Supabase and Neon."""
    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql+psycopg://", 1)
    elif value.startswith("postgresql://"):
        value = value.replace("postgresql://", "postgresql+psycopg://", 1)
    elif value.startswith("postgresql+psycopg2://"):
        value = value.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if ("supabase.co" in value or "pooler.supabase.com" in value or "neon.tech" in value) and "sslmode=" not in value:
        separator = "&" if "?" in value else "?"
        value = f"{value}{separator}sslmode=require"
    return value


db_url = _sqlalchemy_database_url(settings.database_url)
is_serverless = bool(
    os.getenv("VERCEL")
    or os.getenv("VERCEL_ENV")
    or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
    or os.getenv("SINGLE_DATABASE_MODE", "").lower() in ("1", "true", "yes")
    or "pooler.supabase.com" in db_url
    or "supabase.co" in db_url
    or "neon.tech" in db_url
)
engine_kwargs: dict = {"pool_pre_ping": True}
if not db_url.startswith("sqlite"):
    pool_size = 2 if is_serverless else 5
    max_overflow = 3 if is_serverless else 10
    connect_timeout = 10 if is_serverless else 30
    engine_kwargs.update({
        "pool_recycle": 300,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "connect_args": {"connect_timeout": connect_timeout},
        "use_insertmanyvalues": False,
    })
else:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(db_url, **engine_kwargs)
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
                except JWTError as exc:
                    logger.warning("JWT decode failed in get_db for path %s: %s", request.url.path, exc)
                    payload = {}
                except Exception as exc:
                    logger.warning("Unexpected error decoding token in get_db: %s", exc)
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
                    else:
                        logger.warning("Tenant user %s from token not found in database", payload.get("sub"))
                elif token and not payload:
                    logger.warning("Token provided for %s but payload was invalid", request.url.path)
        yield db
    finally:
        db.close()
