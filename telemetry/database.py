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
#define path 
# DB_PATH = Path("db/telemetry.db")
# #ensure the directory exists
# DB_PATH.parent.mkdir(parents=True, exist_ok=True)
# #create the connection 
# def get_connection():
#     conn = sqlite3.connect(DB_PATH)
#     return conn

#initialize the database with the schema
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

#function to insert the telemetry data into the database
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

#query latest records
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
DB_DIR  = Path("./db")
DB_PATH = DB_DIR / "telemetry.db"

@contextmanager
def get_connection():
    """
    Context manager for SQLite connections.
    Ensures connections are always closed, even if an error occurs.
 
    Usage:
        with get_connection() as conn:
            conn.execute(...)
    """
    DB_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # access columns by name, e.g. row["sensor"]
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Create the telemetry table if it doesn't already exist.
    Safe to call multiple times — CREATE TABLE IF NOT EXISTS is idempotent.
    """
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                sensor    TEXT    NOT NULL,
                value     REAL    NOT NULL,
                status    TEXT    NOT NULL
            );
        """)
        # Index on sensor + timestamp speeds up history queries dramatically
        # as the table grows (Phase B Week 2 will query this heavily)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensor_timestamp
            ON telemetry (sensor, timestamp);
        """)
    print(f"[DB] Initialised at {DB_PATH}")
 
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