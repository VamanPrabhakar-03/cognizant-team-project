"""FastAPI Application Main Entrypoint.

Medicare Advantage Risk Adjustment and HCC Documentation Review Assistant API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.config import settings
from src.api.routers import (
    dashboard_router,
    health_router,
    members_router,
    reviews_router,
    suspects_router,
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Backend REST API for Medicare Advantage Risk Adjustment & "
        "HCC Documentation Review Assistant"
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

@app.get("/")
def root():
    """Root API Welcome endpoint."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
    }
