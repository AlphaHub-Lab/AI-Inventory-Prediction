from pathlib import Path
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="Multi-Tenant AI-Powered Inventory Management System with Dynamic PostgreSQL Routing, OCR Receipt Ingestion, Reorder Workflow, and Multi-Level RBAC."
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


@app.on_event("startup")
def apply_schema_migrations() -> None:
    import os
    if os.getenv("SKIP_ALEMBIC_STARTUP") == "1" or settings.skip_alembic_startup or "inventory_system" in settings.database_url:
        return
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
    except Exception as e:
        print(f"Warning on startup migration: {e}")


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": str(exc.detail), "status": exc.status_code}}
    )


@app.get("/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "database": "Supabase PostgreSQL Multi-Tenant",
        "roles": ["admin", "business_owner", "associate"],
        "business_types": ["grocery", "medical", "stationery", "restaurant", "food", "dairy", "clothing", "others"]
    }


# Include sub-routers first so more specific paths match
app.include_router(receipts_router)
app.include_router(reorders_router)
app.include_router(catalog_router)
app.include_router(associate_router)
app.include_router(admin_system_router)
app.include_router(inventory_system_router)
app.include_router(api)
