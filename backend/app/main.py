from contextlib import asynccontextmanager
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

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not (os.getenv("SKIP_ALEMBIC_STARTUP") == "1" or settings.skip_alembic_startup or "inventory_system" in settings.database_url):
        try:
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            command.upgrade(config, "head")
        except Exception as e:
            print(f"Warning on startup migration: {e}")
    try:
        from .seed import seed
        seed()
    except Exception as e:
        print(f"Warning on startup database seeding: {e}")
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
    if any(k in err_lower for k in ["connection refused", "could not translate host name", "operationalerror", "connection to server at", "password authentication failed", "ssl connection", "relation does not exist", "undefinedtable"]):
        return JSONResponse(
            status_code=503,
            content={"error": {"message": "Database error: Unable to connect or initialize. Please check your DATABASE_URL in Vercel Project Settings.", "status": 503}}
        )
    return JSONResponse(
        status_code=500,
        content={"error": {"message": f"Server error: {err_str}", "status": 500}}
    )


@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "service": settings.app_name}


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
