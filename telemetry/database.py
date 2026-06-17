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
DB_PATH = Path("db/telemetry.db")
#ensure the directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
#create the connection 
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn

#initialize the database with the schema
def init_db():
    #make connection 
    conn = get_connection()
    #create a cursor and execute the schema creation query
    #Cursor acts like a SQL command executor. It allows you to execute SQL commands and queries against the database.
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            sensor TEXT,
            value REAL,
            status TEXT
        );
    """)
    conn.commit()
    conn.close()

#function to insert the telemetry data into the database
def insert_telemetry(timestamp, sensor, value, status):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO telemetry(timestamp, sensor, value, status)
    VALUES (?, ?, ?, ?)
    """, (timestamp, sensor, value, status))

    conn.commit()
    conn.close()
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
def get_latest(limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM telemetry
    ORDER BY id DESC
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()

    conn.close()

    return rows