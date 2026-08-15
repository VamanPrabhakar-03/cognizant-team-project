import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

ENV_PATHS = [
    BACKEND_DIR / ".env",
    PROJECT_ROOT / ".env",
]

for env_path in ENV_PATHS:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        break

def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "cognizant_risk_db")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")
    sslmode = os.getenv("DB_SSLMODE", "require" if "azure" in host.lower() else None)

    params = []
    if sslmode:
        params.append(f"sslmode={sslmode}")

    query_str = f"?{'&'.join(params)}" if params else ""
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}{query_str}"
