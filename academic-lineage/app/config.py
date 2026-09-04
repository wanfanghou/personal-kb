"""Path and limit configuration for the lineage app."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Fetch limits (applied to user-submitted URLs only)
FETCH_TIMEOUT_SECONDS = 8
FETCH_MAX_BYTES = 1024 * 1024  # 1 MiB
FETCH_MAX_REDIRECTS = 3
MAX_URL_LENGTH = 2048

# Lineage / year limits
MAX_LINEAGE_DEPTH = 10
MIN_YEAR = 1900


class Config:
    HOST = "127.0.0.1"
    PORT = 5050
    DATABASE = str(BASE_DIR / "data" / "network.sqlite")
    PUBLIC_DATA_DIR = str(BASE_DIR / "public" / "data")
