"""API Configuration Module."""

import os
from typing import List


class APIConfig:
    """FastAPI Application Configuration Settings."""

    PROJECT_NAME: str = "Medicare Advantage Risk Adjustment & HCC Documentation Review Assistant"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # Server configuration
    HOST: str = os.getenv("API_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("API_DEBUG", "True").lower() in ("true", "1", "t")

    # CORS configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "*",
    ]

    # Default Pagination Settings
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


settings = APIConfig()
