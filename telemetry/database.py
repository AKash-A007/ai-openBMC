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