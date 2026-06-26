# this is for the database  == all database operations
"""
never write SQL queries in different files
"""

"""
    Why did you add SQLite?
    The diagnosis agent in Phase A was stateless and only analyzed current events. To support anomaly detection and predictive maintenance,
      I needed historical telemetry.
      I designed a telemetry storage layer using SQLite to persist
     sensor data over time, enabling trend analysis and future machine learning models.
"""
"""
    why sqlite?
    its python ready
    server less
    single file database 
    perfect for edge devices (IMP)
    why is it perfect for edge devices?
    - lightweight and minimal setup, ideal for resource-constrained environments.
    - no need for a separate database server, reducing overhead and complexity.
    - efficient for small to medium-sized datasets, which is typical for edge applications.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

# schema i want to use
"""
    CREATE TABLE telemetry(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    sensor TEXT,
    value REAL,
    status TEXT
);
"""
# define path
# DB_PATH = Path("db/telemetry.db")
# #ensure the directory exists
# DB_PATH.parent.mkdir(parents=True, exist_ok=True)
# #create the connection
# def get_connection():
#     conn = sqlite3.connect(DB_PATH)
#     return conn

# initialize the database with the schema
# def init_db():
#     #make connection
#     conn = get_connection()
#     #create a cursor and execute the schema creation query
#     #Cursor acts like a SQL command executor. It allows you to execute SQL commands and queries against the database.
#     cursor = conn.cursor()
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS telemetry(
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             timestamp TEXT,
#             sensor TEXT,
#             value REAL,
#             status TEXT
#         );
#     """)
#     conn.commit()
#     conn.close()

# function to insert the telemetry data into the database
# def insert_telemetry(timestamp, sensor, value, status):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#     INSERT INTO telemetry(timestamp, sensor, value, status)
#     VALUES (?, ?, ?, ?)
#     """, (timestamp, sensor, value, status))

#     conn.commit()
#     conn.close()
"""Why Use ? Placeholders?

Bad:

cursor.execute(
f"INSERT INTO telemetry VALUES ({value})"
)

Dangerous.

Can lead to SQL Injection.

Good:

VALUES (?, ?, ?, ?)

SQLite safely substitutes values.

This is called:

Parameterized Query

Industry standard."""

# query latest records
# def get_latest(limit=10):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#     SELECT *
#     FROM telemetry
#     ORDER BY id DESC
#     LIMIT ?
#     """, (limit,))

#     rows = cursor.fetchall()

#     conn.close()

#     return rows
# DB_DIR  = Path("./db")
# DB_PATH = DB_DIR / "telemetry.db"

# @contextmanager
# def get_connection():
#     """
#     Context manager for SQLite connections.
#     Ensures connections are always closed, even if an error occurs.

#     Usage:
#         with get_connection() as conn:
#             conn.execute(...)
#     """
#     DB_DIR.mkdir(exist_ok=True)
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row   # access columns by name, e.g. row["sensor"]
#     try:
#         yield conn
#         conn.commit()
#     except Exception:
#         conn.rollback()
#         raise
#     finally:
#         conn.close()


# def init_db() -> None:
#     """
#     Create the telemetry table if it doesn't already exist.
#     Safe to call multiple times — CREATE TABLE IF NOT EXISTS is idempotent.
#     """
#     with get_connection() as conn:
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS telemetry (
#                 id        INTEGER PRIMARY KEY AUTOINCREMENT,
#                 timestamp TEXT    NOT NULL,
#                 sensor    TEXT    NOT NULL,
#                 value     REAL    NOT NULL,
#                 status    TEXT    NOT NULL
#             );
#         """)
#         # Index on sensor + timestamp speeds up history queries dramatically
#         # as the table grows (Phase B Week 2 will query this heavily)
#         conn.execute("""
#             CREATE INDEX IF NOT EXISTS idx_sensor_timestamp
#             ON telemetry (sensor, timestamp);
#         """)
#     print(f"[DB] Initialised at {DB_PATH}")

#  # ── Insert ──────────────────────────────────────────────────────────────────

# def insert_reading(timestamp: str, sensor: str, value: float, status: str) -> int:
#     """
#     Insert a single telemetry reading.
#     Returns the auto-generated row id.
#     """
#     with get_connection() as conn:
#         cursor = conn.execute(
#             """
#             INSERT INTO telemetry (timestamp, sensor, value, status)
#             VALUES (?, ?, ?, ?)
#             """,
#             (timestamp, sensor, value, status),
#         )
#         return cursor.lastrowid


# def insert_readings_batch(readings: list[dict]) -> int:
#     """
#     Insert multiple readings in one transaction — faster than calling
#     insert_reading() in a loop because it avoids repeated commits.

#     readings: [{"timestamp": ..., "sensor": ..., "value": ..., "status": ...}, ...]
#     Returns the number of rows inserted.
#     """
#     with get_connection() as conn:
#         conn.executemany(
#             """
#             INSERT INTO telemetry (timestamp, sensor, value, status)
#             VALUES (:timestamp, :sensor, :value, :status)
#             """,
#             readings,
#         )
#         return len(readings)


# # ── Query (raw — query.py wraps these with friendlier functions) ───────────

# def fetch_all() -> list[sqlite3.Row]:
#     """Return every row in the telemetry table. Use sparingly — table grows fast."""
#     with get_connection() as conn:
#         cursor = conn.execute("SELECT * FROM telemetry ORDER BY id ASC")
#         return cursor.fetchall()


# def fetch_by_sensor(sensor: str, limit: int = 100) -> list[sqlite3.Row]:
#     """
#     Return the most recent `limit` readings for a given sensor,
#     oldest to newest (so plotting/trend functions read naturally left→right).
#     """
#     with get_connection() as conn:
#         cursor = conn.execute(
#             """
#             SELECT * FROM (
#                 SELECT * FROM telemetry
#                 WHERE sensor = ?
#                 ORDER BY id DESC
#                 LIMIT ?
#             )
#             ORDER BY id ASC
#             """,
#             (sensor, limit),
#         )
#         return cursor.fetchall()


# def count_rows() -> int:
#     """Return total number of telemetry rows stored."""
#     with get_connection() as conn:
#         cursor = conn.execute("SELECT COUNT(*) as count FROM telemetry")
#         return cursor.fetchone()["count"]


# def clear_table() -> None:
#     """Wipe all telemetry data. Use for testing only."""
#     with get_connection() as conn:
#         conn.execute("DELETE FROM telemetry")
#     print("[DB] Telemetry table cleared.")


# # ── Self-test ───────────────────────────────────────────────────────────────

# if __name__ == "__main__":
#     init_db()
#     print(f"[DB] Current row count: {count_rows()}")

"""
telemetry/database.py

Database Layer — Phase B Week 1
All SQLite operations live here. Never write raw SQL in collector.py
or query.py — they import from this module instead.

Why centralise SQL in one file?
  - Single source of truth for schema
  - Easy to swap SQLite → PostgreSQL later (only this file changes)
  - Prevents SQL injection bugs scattered across files
  - Standard practice: separate data access layer from business logic
"""

import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

# ── Constants ───────────────────────────────────────────────────────────────

DB_DIR = Path(__file__).resolve().parent.parent / "db"
DB_PATH = DB_DIR / "telemetry.db"
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()


# ── Compatible Interface for SQLite & PostgreSQL ─────────────────────────────


class CompatibleRow:
    def __init__(self, dict_row):
        self._row = dict_row

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._row.values())[key]
        return self._row[key]

    def keys(self):
        return list(self._row.keys())

    def get(self, key, default=None):
        return self._row.get(key, default)

    def items(self):
        return self._row.items()

    def __iter__(self):
        return iter(self._row.items())


class CompatibleCursor:
    def __init__(self, cursor, is_postgres: bool):
        self.cursor = cursor
        self.is_postgres = is_postgres

    def execute(self, sql, params=None):
        if params is None:
            params = ()
        if self.is_postgres:
            import re

            sql = sql.replace("?", "%s")
            sql = re.sub(r":(\w+)", r"%(\1)s", sql)
        self.cursor.execute(sql, params)
        return self

    def executemany(self, sql, params_list):
        if self.is_postgres:
            import re

            sql = sql.replace("?", "%s")
            sql = re.sub(r":(\w+)", r"%(\1)s", sql)
        self.cursor.executemany(sql, params_list)
        return self

    def fetchall(self):
        rows = self.cursor.fetchall()
        if self.is_postgres:
            return [CompatibleRow(row) for row in rows]
        return rows

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is not None and self.is_postgres:
            return CompatibleRow(row)
        return row

    @property
    def lastrowid(self):
        if self.is_postgres:
            # Get last auto-generated serial ID on this connection
            self.cursor.execute("SELECT lastval();")
            return self.cursor.fetchone()[0]
        else:
            return self.cursor.lastrowid


class CompatibleConnection:
    def __init__(self, conn, is_postgres: bool):
        self.conn = conn
        self.is_postgres = is_postgres

    def cursor(self):
        if self.is_postgres:
            return CompatibleCursor(
                self.conn.cursor(cursor_factory=RealDictCursor), is_postgres=True
            )
        return CompatibleCursor(self.conn.cursor(), is_postgres=False)

    def execute(self, sql, params=None):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor

    def executemany(self, sql, params_list):
        cursor = self.cursor()
        cursor.executemany(sql, params_list)
        return cursor

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()


# ── Connection management ──────────────────────────────────────────────────


def get_connection():
    """
    Returns a unified connection wrapper for SQLite or PostgreSQL.
    Usage:
        with get_connection() as conn:
            conn.execute(...)
    """
    if DB_TYPE == "postgres":
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is not installed but DB_TYPE=postgres was specified."
            )
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "postgres")
        dbname = os.getenv("DB_NAME", "telemetry")
        raw_conn = psycopg2.connect(
            host=host, port=port, user=user, password=password, dbname=dbname
        )
        return CompatibleConnection(raw_conn, is_postgres=True)
    else:
        DB_DIR.mkdir(exist_ok=True)
        raw_conn = sqlite3.connect(DB_PATH)
        raw_conn.row_factory = sqlite3.Row
        return CompatibleConnection(raw_conn, is_postgres=False)


# ── Schema ──────────────────────────────────────────────────────────────────


def init_db() -> None:
    """
    Create the telemetry and diagnoses tables if they don't already exist.
    Safe to call multiple times.
    """
    with get_connection() as conn:
        if DB_TYPE == "postgres":
            # PostgreSQL Schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id        SERIAL PRIMARY KEY,
                    timestamp TEXT    NOT NULL,
                    sensor    TEXT    NOT NULL,
                    value     DOUBLE PRECISION NOT NULL,
                    status    TEXT    NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS diagnoses (
                    id         SERIAL PRIMARY KEY,
                    timestamp  TEXT    NOT NULL,
                    sensor     TEXT    NOT NULL,
                    root_cause TEXT    NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          SERIAL PRIMARY KEY,
                    timestamp   TEXT    NOT NULL,
                    issue       TEXT    NOT NULL,
                    sensor      TEXT    NOT NULL DEFAULT 'UNKNOWN',
                    action      TEXT    NOT NULL,
                    executed_by TEXT    NOT NULL DEFAULT 'system',
                    policy      TEXT    NOT NULL DEFAULT 'AUTO',
                    status      TEXT    NOT NULL,
                    severity    TEXT    NOT NULL DEFAULT 'UNKNOWN',
                    details     TEXT,
                    duration_ms DOUBLE PRECISION DEFAULT 0
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_requests (
                    id           TEXT    PRIMARY KEY,
                    issue        TEXT    NOT NULL,
                    action       TEXT    NOT NULL,
                    sensor       TEXT    NOT NULL,
                    severity     TEXT    NOT NULL,
                    policy       TEXT    NOT NULL,
                    status       TEXT    NOT NULL DEFAULT 'PENDING',
                    requested_at TEXT    NOT NULL,
                    resolved_at  TEXT,
                    resolved_by  TEXT,
                    notes        TEXT    DEFAULT ''
                );
            """)
        else:
            # SQLite Schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT    NOT NULL,
                    sensor    TEXT    NOT NULL,
                    value     REAL    NOT NULL,
                    status    TEXT    NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS diagnoses (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp  TEXT    NOT NULL,
                    sensor     TEXT    NOT NULL,
                    root_cause TEXT    NOT NULL,
                    confidence REAL    NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    issue       TEXT    NOT NULL,
                    sensor      TEXT    NOT NULL DEFAULT 'UNKNOWN',
                    action      TEXT    NOT NULL,
                    executed_by TEXT    NOT NULL DEFAULT 'system',
                    policy      TEXT    NOT NULL DEFAULT 'AUTO',
                    status      TEXT    NOT NULL,
                    severity    TEXT    NOT NULL DEFAULT 'UNKNOWN',
                    details     TEXT,
                    duration_ms REAL    DEFAULT 0
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_requests (
                    id           TEXT    PRIMARY KEY,
                    issue        TEXT    NOT NULL,
                    action       TEXT    NOT NULL,
                    sensor       TEXT    NOT NULL,
                    severity     TEXT    NOT NULL,
                    policy       TEXT    NOT NULL,
                    status       TEXT    NOT NULL DEFAULT 'PENDING',
                    requested_at TEXT    NOT NULL,
                    resolved_at  TEXT,
                    resolved_by  TEXT,
                    notes        TEXT    DEFAULT ''
                );
            """)

        # Indexes are the same for both DBs
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensor_timestamp
            ON telemetry (sensor, timestamp);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_diagnoses_sensor_timestamp
            ON diagnoses (sensor, timestamp);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_log (timestamp);
        """)

    if DB_TYPE == "postgres":
        print(f"[DB] Initialised PostgreSQL database")
    else:
        print(f"[DB] Initialised SQLite at {DB_PATH}")


# ── Diagnoses table operations ────────────────────────────────────────────────


def insert_diagnosis(
    timestamp: str, sensor: str, root_cause: str, confidence: float
) -> int:
    """
    Record a single diagnosis result (e.g. from Phase A's RAG+LLM agent,
    or any future predictor) into permanent RCA history.
    Returns the auto-generated row id.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO diagnoses (timestamp, sensor, root_cause, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (timestamp, sensor, root_cause, confidence),
        )
        return cursor.lastrowid


def fetch_recent_diagnoses(limit: int = 10) -> list[sqlite3.Row]:
    """Return the most recent N diagnoses, newest first — for a 'Recent Diagnoses' panel."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM diagnoses ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cursor.fetchall()


def fetch_diagnoses_by_sensor(sensor: str, limit: int = 50) -> list[sqlite3.Row]:
    """Return diagnosis history for one specific sensor, newest first."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM diagnoses WHERE sensor = ? ORDER BY id DESC LIMIT ?",
            (sensor, limit),
        )
        return cursor.fetchall()


def count_diagnoses() -> int:
    """Total number of diagnoses ever recorded."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) as count FROM diagnoses")
        return cursor.fetchone()["count"]


# ── Insert ──────────────────────────────────────────────────────────────────


def insert_reading(timestamp: str, sensor: str, value: float, status: str) -> int:
    """
    Insert a single telemetry reading.
    Returns the auto-generated row id.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO telemetry (timestamp, sensor, value, status)
            VALUES (?, ?, ?, ?)
            """,
            (timestamp, sensor, value, status),
        )
        return cursor.lastrowid


def insert_readings_batch(readings: list[dict]) -> int:
    """
    Insert multiple readings in one transaction — faster than calling
    insert_reading() in a loop because it avoids repeated commits.

    readings: [{"timestamp": ..., "sensor": ..., "value": ..., "status": ...}, ...]
    Returns the number of rows inserted.
    """
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO telemetry (timestamp, sensor, value, status)
            VALUES (:timestamp, :sensor, :value, :status)
            """,
            readings,
        )
        return len(readings)


# ── Query (raw — query.py wraps these with friendlier functions) ───────────


def fetch_all() -> list[sqlite3.Row]:
    """Return every row in the telemetry table. Use sparingly — table grows fast."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM telemetry ORDER BY id ASC")
        return cursor.fetchall()


def fetch_by_sensor(sensor: str, limit: int = 100) -> list[sqlite3.Row]:
    """
    Return the most recent `limit` readings for a given sensor,
    oldest to newest (so plotting/trend functions read naturally left→right).
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM telemetry
                WHERE sensor = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (sensor, limit),
        )
        return cursor.fetchall()


def count_rows() -> int:
    """Return total number of telemetry rows stored."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) as count FROM telemetry")
        return cursor.fetchone()["count"]


def clear_table() -> None:
    """Wipe all telemetry data. Use for testing only."""
    with get_connection() as conn:
        conn.execute("DELETE FROM telemetry")
    print("[DB] Telemetry table cleared.")


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print(f"[DB] Current row count: {count_rows()}")
