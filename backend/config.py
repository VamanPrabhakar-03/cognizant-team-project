import os
from pathlib import Path
from typing import List
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

for env_path in [BACKEND_DIR / ".env", PROJECT_ROOT / ".env"]:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        break


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
