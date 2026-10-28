from contextlib import asynccontextmanager
import logging
import os
import secrets
from pathlib import Path
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .config import get_settings
from .routers.api import api
from .routers.receipts_router import router as receipts_router
from .routers.reorders_router import router as reorders_router
from .routers.catalog_router import router as catalog_router
from .routers.associate_management_router import router as associate_router
from .routers.admin_management_router import router as admin_system_router
from .routers.inventory_system_router import router as inventory_system_router
from .rate_limit import limiter
from .db import engine

logger = logging.getLogger("main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure schema compatibility (auto-heals missing columns like owner_phone & tables on Vercel/Supabase)
    try:
        from .schema_migration import ensure_schema_compatibility
        ensure_schema_compatibility(engine)
    except Exception as e:
        logger.error("Notice on schema compatibility check: %s", e, exc_info=True)

    # In serverless environments like Vercel, avoid long-running migrations and seeding during cold start
    is_serverless = bool(
        os.getenv("VERCEL")
        or os.getenv("VERCEL_ENV")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("SINGLE_DATABASE_MODE", "").lower() in ("1", "true", "yes")
        or "pooler.supabase.com" in settings.database_url.lower()
        or "supabase.co" in settings.database_url.lower()
        or "neon.tech" in settings.database_url.lower()
    )
    is_production = settings.environment.lower() in ("production", "prod") or os.getenv("VERCEL_ENV") == "production"
    if not is_serverless and not (os.getenv("SKIP_ALEMBIC_STARTUP") == "1" or settings.skip_alembic_startup or "inventory_system" in settings.database_url):
        try:
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            command.upgrade(config, "head")
        except Exception as e:
            logger.warning("Warning on startup migration: %s", e)
    if not is_serverless and not is_production and not (os.getenv("SKIP_SEEDING_STARTUP") == "1"):
        try:
            from .seed import seed
            seed()
        except Exception as e:
            logger.warning("Warning on startup database seeding: %s", e)
    else:
        logger.info(
            "Skipping startup database seeding (is_serverless=%s, is_production=%s, skip_flag=%s)",
            is_serverless, is_production, os.getenv("SKIP_SEEDING_STARTUP") == "1"
        )
    yield
    # Shutdown


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="Multi-Tenant AI-Powered Inventory Management System with Dynamic PostgreSQL Routing, OCR Receipt Ingestion, Reorder Workflow, and Multi-Level RBAC.",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": str(exc.detail), "status": exc.status_code}}
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    err_str = str(exc)
    err_lower = err_str.lower()
    exc_type = type(exc).__name__.lower()
    is_prod = settings.environment.lower() in ("production", "prod")

    logger.exception("Unhandled server exception: %s", exc)

    if (
        "operationalerror" in exc_type
        or "programmingerror" in exc_type
        or "undefinedcolumn" in err_lower
        or "undefinedtable" in err_lower
        or "relation does not exist" in err_lower
        or "column does not exist" in err_lower
        or "infailedsqltransaction" in err_lower
        or "syntax error" in err_lower
        or "statement error" in err_lower
        or "timeout" in err_lower
        or any(k in err_lower for k in [
            "connection refused", "could not translate host name", "operationalerror",
            "connection to server at", "password authentication failed", "ssl connection",
            "relation does not exist", "undefinedtable", "timeout", "timed out", "psycopg"
        ])
    ):
        return JSONResponse(
            status_code=503,
            content={"error": {"message": "Database temporary unavailability or initialization in progress. Please retry momentarily.", "status": 503}}
        )

    # In any environment, suppress raw SQL error text from API responses
    sql_keywords = ("select ", "insert ", "update ", "delete ", "alter table", "create table", "psycopg", "syntax error at or near", "column ", "relation ")
    if any(kw in err_lower for kw in sql_keywords):
        return JSONResponse(
            status_code=503,
            content={"error": {"message": "Database service is initializing or temporarily busy. Please refresh in a moment.", "status": 503}}
        )

    user_msg = "An unexpected server error occurred. Please contact system administrator." if is_prod else f"Server error: {err_str}"
    return JSONResponse(
        status_code=500,
        content={"error": {"message": user_msg, "status": 500}}
    )


@app.get("/ping", tags=["system"])
@app.get("/api/ping", tags=["system"])
def ping():
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "service": settings.app_name, "database": "connected"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "error": "Database unavailable", "detail": str(exc)}
        )


@app.post("/desktop/shutdown", tags=["system"], include_in_schema=False)
def desktop_shutdown(request: Request, x_desktop_shutdown_token: str = Header(default="")):
    expected = os.getenv("DESKTOP_SHUTDOWN_TOKEN", "")
    client_host = request.client.host if request.client else ""
    if not expected or client_host not in {"127.0.0.1", "::1"} or not secrets.compare_digest(x_desktop_shutdown_token, expected):
        raise HTTPException(status_code=403, detail="Forbidden")
    server = getattr(request.app.state, "desktop_server", None)
    if server is None:
        raise HTTPException(status_code=503, detail="Desktop shutdown is unavailable")
    server.should_exit = True
    return {"status": "shutting_down"}


# Include sub-routers first so more specific paths match
app.include_router(receipts_router)
app.include_router(reorders_router)
app.include_router(catalog_router)
app.include_router(associate_router)
app.include_router(admin_system_router)
app.include_router(inventory_system_router)
app.include_router(api)
