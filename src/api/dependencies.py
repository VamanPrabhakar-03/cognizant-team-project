"""FastAPI Dependencies Module.

Reuses the existing database session dependency from src/database/session.py.
"""

from src.database.session import get_db

__all__ = ["get_db"]
