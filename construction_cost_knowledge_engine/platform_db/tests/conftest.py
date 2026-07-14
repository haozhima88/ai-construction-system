from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine


@pytest.fixture(scope="session")
def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration tests")
    return value


@pytest.fixture(scope="session")
def engine(database_url):
    instance = create_engine(database_url, pool_pre_ping=True)
    yield instance
    instance.dispose()


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[3]

