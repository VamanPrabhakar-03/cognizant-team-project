"""FastAPI Application Main Entrypoint.

Medicare Advantage Risk Adjustment and HCC Documentation Review Assistant API.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import (
    dashboard_router,
    health_router,
    members_router,
    reviews_router,
    suspects_router,
    pipeline_router,
    llm_reviews_router,
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Backend REST API for Medicare Advantage Risk Adjustment & "
        "HCC Documentation Suspecting Assistant"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(health_router)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)
app.include_router(members_router, prefix=settings.API_V1_STR)
app.include_router(suspects_router, prefix=settings.API_V1_STR)
app.include_router(reviews_router, prefix=settings.API_V1_STR)
app.include_router(pipeline_router, prefix=settings.API_V1_STR)
app.include_router(llm_reviews_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    """Root API Welcome endpoint."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
    }
