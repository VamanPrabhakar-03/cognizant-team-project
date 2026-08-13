"""Routers Package Init."""

from .dashboard import router as dashboard_router
from .health import router as health_router
from .members import router as members_router
from .reviews import router as reviews_router
from .suspects import router as suspects_router

__all__ = [
    "health_router",
    "dashboard_router",
    "members_router",
    "suspects_router",
    "reviews_router",
]
