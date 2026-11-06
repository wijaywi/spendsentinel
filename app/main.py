"""SpendSentinel - AI-agent commerce guard with PayPal Sandbox integration.

Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, Any
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db as init_validation_db
from app.config import settings
from app.models.database import init_db as init_async_db
from app.core.database import init_db, SessionLocal
from app.core.seed import seed_database
from app.api.evidence import router as evidence_router
from app.api.dashboard import router as dashboard_router
from app.api.agents import router as agents_router
from app.api.validation import router as validation_router
from app.api.integrations import router as integrations_router
from app.api.integrations import webhook_router as paypal_webhook_router
from app.security import authenticated_user


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Execute startup and shutdown lifecycle hooks."""
    # Initialize DB tables
    init_db()
    init_validation_db()
    await init_async_db()

    # Seed baseline demo dataset
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

    yield


STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"

app = FastAPI(
    title="SpendSentinel API",
    description="AI-agent commerce safety prototype with deterministic spending policies and PayPal Sandbox checkout.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for browser frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
api_dependencies = [Depends(authenticated_user)]
app.include_router(evidence_router, dependencies=api_dependencies)
app.include_router(dashboard_router, dependencies=api_dependencies)
app.include_router(agents_router, dependencies=api_dependencies)
app.include_router(validation_router, dependencies=api_dependencies)
app.include_router(integrations_router, dependencies=api_dependencies)
app.include_router(paypal_webhook_router)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    """Serve the local interactive Sentinel demo."""
    return FileResponse(STATIC_INDEX)


@app.get("/api/status", tags=["Health"])
def root() -> Dict[str, Any]:
    """Root health check and platform status."""
    return {
        "platform": "SpendSentinel",
        "status": "OPERATIONAL",
        "modules": [
            "International Payment Validator",
            "AI Agent Guard",
            "AI Natural-Language Purchase Extraction",
            "Evidence Vault (DPS)",
            "Dispute Prevention Shield (CE3.0 inspired)",
            "Dashboard Analytics",
            "PayPal Orders API Sandbox",
        ],
    }


@app.get("/health", tags=["Health"])
def health_check() -> Dict[str, str]:
    """API health probe endpoint."""
    return {"status": "ok"}
