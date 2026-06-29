from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PRIVATE_DATA_DIR = DATA_DIR / "private"
MOCK_DATA_DIR = DATA_DIR / "mock"
DEFAULT_DB_PATH = PRIVATE_DATA_DIR / "cost_engine.sqlite"
