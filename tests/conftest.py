import os
import pytest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Enforce SQLite and set a test database path during test execution
os.environ["DB_TYPE"] = "sqlite"
os.environ["DB_PATH"] = "db/test_telemetry.db"

from telemetry.database import init_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()
    yield
