# 💾 AI OpsBMC — Phase B Week 1: Telemetry Storage Layer
**Date:** 2026-06-17
**Project:** `ai-openBMC`
**Phase:** B — Historical Intelligence
**Stack:** SQLite · Python · Parameterized Queries · Context Managers

---

## 📌 Where We Are

```
Phase A ✅ COMPLETE
├── Week 1: Redfish telemetry collection
├── Week 2: RAG knowledge retrieval
├── Week 3: LLM diagnosis (Qwen3-8B)
└── Week 4: FastAPI + Streamlit production service

Phase B
└── Week 1: Telemetry Storage Layer  ← we are here
    └── Week 2: Anomaly Detection (planned)
```

**Phase A built a system that can diagnose a single event.**
**Phase B builds a system that remembers — because diagnosis without history is guesswork, and prediction is impossible without a trend.**

---

## 🎯 The Core Problem This Week Solves

Phase A's diagnosis agent is **stateless**. Every call to `diagnose()` sees exactly one snapshot:

```json
{"sensor": "CPU_TEMP", "value": 75}
```

The moment the Python process exits, that reading is gone. There is no way to answer questions like:

- "Is this temperature rising or stable?"
- "How long has this sensor been in WARNING state?"
- "What did this sensor look like 10 minutes ago?"

**None of these questions are answerable from a single data point.** They require a *time-series* — and a time-series only exists if every reading is persisted somewhere that survives process restarts.

```
Monitoring  = current state   (Phase A — what Phase A built)
Analytics   = historical state (Phase B Week 1 — what we're building now)
```

This is not a cosmetic addition — it's the foundational layer every later AI capability (anomaly detection, predictive maintenance, trend-aware diagnosis) depends on.

---

## 🗂️ Files Built This Week

```
ai-openBMC/
└── telemetry/
    ├── database.py    ← all SQL lives here, nowhere else
    ├── collector.py   ← generates + persists readings on a timer
    └── query.py       ← read-friendly functions for downstream consumers
└── db/
    └── telemetry.db   ← the actual SQLite file (gitignored)
```

---

## 🧠 Theory & Engineering Decisions

### 1. Why a Database at All?

The naive approach — keep everything in a Python list — looks fine until you think about the lifecycle:

```python
telemetry = []
telemetry.append({"sensor": "CPU_TEMP", "value": 74})
# Program exits → telemetry is gone. Permanently.
```

In-memory state dies with the process. A monitoring system that forgets everything on restart cannot do trend analysis, cannot build training data for ML models, and cannot support root-cause analysis that references "what changed over the last hour."

**The fix is persistence** — writing data to disk in a structured, queryable form so it outlives the process.

---

### 2. Why SQLite Specifically?

There are dozens of database engines. SQLite was the correct choice here for concrete, non-arbitrary reasons:

| Property | Why it matters for this project |
|---|---|
| Serverless | No separate DB process to install, configure, or keep alive |
| Single file | The entire database is `db/telemetry.db` — trivial to back up, move, inspect |
| Ships with Python | `import sqlite3` — zero extra dependencies |
| ACID-compliant | Writes are safe even if the collector crashes mid-insert |
| Edge-device friendly | OpenBMC runs on constrained embedded hardware — no room for a Postgres server |

**The edge-device angle matters specifically for this project.** A real BMC is a tiny ARM SoC with limited RAM and storage. SQLite's "no server, no daemon, no config" model matches that constraint exactly — this is why embedded systems and IoT telemetry pipelines reach for SQLite by default rather than client-server databases.

**When you'd outgrow it:** SQLite handles single-writer workloads beautifully but doesn't support concurrent writes well. If this project later needs multiple collectors writing simultaneously at high frequency, that's the trigger to migrate to PostgreSQL — not before.

---

### 3. Why Centralise SQL in One File (`database.py`)

The anti-pattern to avoid:

```
collector.py   → has its own cursor.execute("INSERT...")
query.py       → has its own cursor.execute("SELECT...")
api.py         → has its own cursor.execute("DELETE...")
```

This is what happens when SQL is scattered: the schema is implicitly duplicated across files. The moment you need to rename a column or add a constraint, you're hunting through every file in the codebase hoping you found every occurrence.

**The fix — Separation of Concerns:** one file owns the schema and all raw SQL. Every other file imports functions and never writes a query directly.

```python
# database.py — the ONLY file that knows SQL syntax
def insert_reading(timestamp, sensor, value, status): ...
def fetch_by_sensor(sensor, limit): ...

# collector.py — calls the function, never touches SQL
from database import insert_reading
insert_reading(ts, "CPU_TEMP", 74.0, "OK")
```

This is the same principle as a repository pattern in larger backend systems — the data access layer is isolated so the rest of the application is decoupled from *how* data is stored. Swapping SQLite for PostgreSQL later means changing one file, not auditing the entire codebase.

---

### 4. Schema Design — Field by Field

```sql
CREATE TABLE telemetry (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT    NOT NULL,
    sensor    TEXT    NOT NULL,
    value     REAL    NOT NULL,
    status    TEXT    NOT NULL
);
```

**`id INTEGER PRIMARY KEY AUTOINCREMENT`**
SQLite generates this automatically — `1, 2, 3, ...`. It gives every row a stable, unique handle independent of its data, which matters once you start deleting or updating rows and need a reliable reference.

**`timestamp TEXT`**
Stored as ISO-8601 (`2026-06-17T15:30:22+00:00`), not as a native datetime type. This is a deliberate SQLite-specific choice — SQLite has no dedicated datetime type, and ISO-8601 strings sort correctly with plain lexicographic `ORDER BY`, which is exactly what `ORDER BY timestamp` needs.

**`sensor TEXT`**
The sensor identifier (`CPU_TEMP`, `FAN_SPEED`, etc.). This is the column every history query filters on — which is why it's indexed (see below).

**`value REAL`**
`REAL` permits decimals (`74.5`, `11.98`), unlike `INTEGER`. Hardware telemetry is rarely a clean integer — voltage and temperature readings need fractional precision.

**`status TEXT`**
The classification (`OK` / `WARNING` / `CRITICAL`) computed by a threshold engine *before* the row is written. Storing the pre-computed status (rather than recomputing it from `value` every time it's read) trades a small amount of redundancy for much faster downstream queries — you don't need sensor-specific threshold logic everywhere that reads telemetry.

---

### 5. The Index — Why It's Not Optional

```sql
CREATE INDEX idx_sensor_timestamp ON telemetry (sensor, timestamp);
```

Without an index, `SELECT * FROM telemetry WHERE sensor = 'CPU_TEMP'` forces SQLite to scan every single row in the table — O(n) — checking each one. At 100 rows this is invisible. At 500,000 rows (a realistic count after weeks of 5-second polling), this becomes the dominant cost of every query.

An index on `(sensor, timestamp)` lets SQLite use a B-tree lookup instead — O(log n). This is the single highest-leverage change you can make to a time-series table, because **every** downstream consumer — Phase B Week 2's anomaly detector, dashboards, the RAG retriever — will filter by sensor and order by time. Adding the index now, before the table grows, costs nothing and avoids a painful retrofit later.

---

### 6. Context Managers — Why `get_connection()` Uses `@contextmanager`

The naive pattern repeats boilerplate everywhere and is fragile:

```python
# Fragile — if an exception happens between connect() and close(), the
# connection leaks and is never released
conn = sqlite3.connect(DB_PATH)
conn.execute(...)
conn.commit()
conn.close()
```

The context manager guarantees the connection is closed **no matter what happens** inside the `with` block — including exceptions:

```python
@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

```python
with get_connection() as conn:
    conn.execute("INSERT INTO telemetry ...")
# Connection is guaranteed closed here — success or failure
```

This is the same `try/finally` discipline you'd apply to any external resource (file handles, network sockets, locks) — acquire, use, **always** release. `conn.row_factory = sqlite3.Row` is a smaller but useful detail: it lets you access columns by name (`row["sensor"]`) instead of by fragile positional index (`row[1]`), which avoids a whole class of bugs when the column order changes.

---

### 7. Parameterized Queries — Why `?` Placeholders Are Mandatory

This is the single most important security concept in this week's work, and it's worth understanding at the mechanism level, not just as a rule to follow.

#### The vulnerability

```python
# DANGEROUS — never do this
sensor = input()
query = f"SELECT * FROM telemetry WHERE sensor = '{sensor}'"
cursor.execute(query)
```

If a normal value is supplied, this works fine:
```sql
SELECT * FROM telemetry WHERE sensor = 'CPU_TEMP'
```

But the string `sensor` is built by **textually splicing** untrusted input directly into SQL syntax. If the input itself contains SQL syntax, that syntax executes:

```
Input:  ' OR 1=1 --

Resulting SQL:
SELECT * FROM telemetry WHERE sensor = '' OR 1=1 --'
```

Walking through this: `''` is an empty string match (false), `OR 1=1` is always true, and `--` comments out everything after it (including the original trailing quote). The database now returns **every row in the table** — the attacker just rewrote the meaning of your query using nothing but a text field.

A more destructive example:
```
Input:  CPU_TEMP'); DROP TABLE telemetry; --

Resulting SQL:
INSERT INTO telemetry VALUES (..., 'CPU_TEMP'); DROP TABLE telemetry; --')
```
This chains a second statement onto the first — the entire table gets dropped.

#### Why this happens

When you use an f-string, **Python builds the complete SQL text before SQLite ever sees it.** By the time SQLite receives the string, there is no way for it to distinguish "this part is code" from "this part is data" — it all looks like one indistinguishable blob of SQL syntax.

#### The fix — parameterized queries

```python
# SAFE
cursor.execute(
    "INSERT INTO telemetry (timestamp, sensor, value, status) VALUES (?, ?, ?, ?)",
    (timestamp, sensor, value, status),
)
```

The `?` placeholders mean the **SQL template** and the **data values** are sent to SQLite as two separate channels — the query structure is compiled first, and the values are substituted afterward as pure data, never as executable syntax.

If an attacker now supplies `' OR 1=1 --` as the `sensor` value:

```python
cursor.execute(
    "SELECT * FROM telemetry WHERE sensor = ?",
    ("' OR 1=1 --",),
)
```

SQLite searches for a row where `sensor` literally **equals the string** `' OR 1=1 --` — character for character, including the quote marks. No such sensor exists, so the query returns nothing. The malicious input is inert; it can only ever be data, never code.

#### Visual summary

```
Vulnerable (string formatting):
    SQL + User Input  →  Merged into one string  →  Database executes everything

Safe (parameterized query):
    SQL Template  +  Data (separate channel)  →  Database knows the difference
                                                →  Data cannot become code
```

#### Why this matters even with "trusted" data

In this project, sensor names currently come from Redfish or a mock generator — not directly from an end user. It would be easy to reason "this isn't user input, so it's fine to skip parameterization here." That reasoning is exactly how vulnerabilities get introduced later: the moment this telemetry pipeline gains a web dashboard, a REST endpoint accepting external sensor data, or a file upload feature, any SQL written without placeholders becomes an injection vector. **Building the habit now — even where the immediate risk is low — means the codebase is safe by default as it grows**, rather than safe only by accident.

This is why parameterized queries are the universal standard across SQLite, PostgreSQL, MySQL, SQL Server, and every major ORM (SQLAlchemy, Django ORM) — it is not a SQLite-specific quirk, it is the baseline expectation for any code that touches a database.

---

### 8. Threshold-Based Status Classification

Each sensor in `collector.py` has its own realistic value range and thresholds — deliberately mirroring how real hardware exposes health status via Redfish's `Status.Health` field (`OK` / `Warning` / `Critical`):

```python
SENSORS = {
    "CPU_TEMP":   {"min": 55, "max": 90, "warning_at": 80, "critical_at": 90},
    "FAN_SPEED":  {"min": 2000, "max": 6000, "warning_at": 2500,
                   "critical_at": 2200, "inverted": True},
}
```

**The `inverted` flag matters.** For temperature and voltage, *higher* is worse. For fan speed, it's the opposite — a fan spinning *too slowly* is the failure mode, not too fast. Encoding this per-sensor instead of assuming "high = bad" universally avoids a subtle correctness bug that would otherwise misclassify a dying fan as healthy.

```python
def _determine_status(sensor_name, value):
    spec = SENSORS[sensor_name]
    if spec.get("inverted"):
        if value <= spec["critical_at"]: return "CRITICAL"
        elif value <= spec["warning_at"]: return "WARNING"
        return "OK"
    if value >= spec["critical_at"]: return "CRITICAL"
    elif value >= spec["warning_at"]: return "WARNING"
    return "OK"
```

This logic transfers directly when the mock generator is later replaced with live Redfish polling — the threshold engine doesn't care where the raw value came from.

---

### 9. Polling — Why Continuous, Not One-Shot

```python
def run_forever(interval=5):
    while True:
        collect_once()
        time.sleep(interval)
```

A monitoring system that runs once and exits is not a monitoring system — it's a single snapshot. Every production telemetry tool (Prometheus, Nagios, Zabbix, Datadog agents) works the same way: **poll on a fixed interval, forever, until explicitly stopped.**

The interval is a tunable trade-off:

| Interval | Trade-off |
|---|---|
| 5 seconds | Fast feedback for testing, but generates rows quickly — fine for dev |
| 30+ seconds | Lower storage growth rate, appropriate for long-running production monitoring |

This project uses 5 seconds during development specifically so trends become visible within minutes rather than requiring hours of waiting.

---

### 10. Batch Insert — `executemany()` vs a Loop

```python
def insert_readings_batch(readings: list[dict]) -> int:
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO telemetry (timestamp, sensor, value, status) "
            "VALUES (:timestamp, :sensor, :value, :status)",
            readings,
        )
        return len(readings)
```

Calling `insert_reading()` in a loop opens a transaction, writes one row, and commits — four sensors means four separate commits per polling cycle. `executemany()` batches all inserts into a single transaction, which is meaningfully faster once you're writing many rows per cycle (as this project does — 4 sensors × every poll). This isn't yet used by the collector (which still inserts one sensor at a time for clarity), but it's available for when polling frequency or sensor count scales up.

---

## 🔁 Complete Data Flow

```
collector.py
    │
    ├── _generate_value(sensor)        ← mock reading (real Redfish later)
    ├── _determine_status(sensor, val) ← threshold classification
    │
    ▼
database.py — insert_reading()
    │
    ├── get_connection()  ← context manager, guaranteed cleanup
    ├── INSERT INTO telemetry (?, ?, ?, ?)  ← parameterized, injection-safe
    │
    ▼
db/telemetry.db   (persists across restarts)
    │
    ▼
query.py — get_sensor_history(sensor)
    │
    ├── database.fetch_by_sensor()  ← uses the (sensor, timestamp) index
    │
    ▼
[ list of floats, oldest → newest ]
    │
    ▼
Phase B Week 2 — Anomaly Detection (next)
```

---

## 🐛 Design Decisions That Prevent Future Bugs

### Decision 1 — `IF NOT EXISTS` on table and index creation
```sql
CREATE TABLE IF NOT EXISTS telemetry (...)
```
Without this guard, calling `init_db()` a second time throws `table telemetry already exists`. Since `init_db()` is called on every collector/query startup (idempotent by design), this guard is what makes repeated startup safe.

### Decision 2 — Oldest-to-newest ordering in `fetch_by_sensor()`
```sql
SELECT * FROM (
    SELECT * FROM telemetry WHERE sensor = ? ORDER BY id DESC LIMIT ?
) ORDER BY id ASC
```
The inner query grabs the most recent N rows efficiently (descending + limit). The outer query re-sorts them ascending. This matters because every downstream consumer — trend calculations, charts, the `get_sensor_stats()` trend logic — assumes "first element is oldest, last is newest." Getting this backwards silently inverts every trend calculation.

### Decision 3 — `row_factory = sqlite3.Row`
Returns rows as dict-like objects (`row["sensor"]`) instead of plain tuples (`row[1]`). This means adding a new column to the schema later doesn't silently break every piece of code that accessed columns by position.

---

## 📦 No New Dependencies

This week deliberately adds zero new pip packages — `sqlite3` is part of the Python standard library. This is itself a design decision worth noting: for a storage layer at this scale, reaching for an ORM (SQLAlchemy) or external DB driver would be premature complexity.

---

## ✅ Week 1 Completion Criteria — Verified

- [x] SQLite database created (`db/telemetry.db`)
- [x] Telemetry table created with schema + index
- [x] Collector inserts records on a timed loop (tested: 3 cycles × 4 sensors = 12 rows)
- [x] Data persists after restart (file-based, confirmed via `sqlite3 db/telemetry.db`)
- [x] Query function returns history as a clean float list
- [x] Can retrieve last N sensor readings via `limit` parameter

```bash
# Manual verification
sqlite3 db/telemetry.db "SELECT * FROM telemetry ORDER BY id DESC LIMIT 5;"
```

---

## 🗓️ Next Steps — Phase B Week 2: Anomaly Detection

- [ ] Feed `get_sensor_history()` output into a statistical anomaly model (z-score / rolling stddev)
- [ ] Define "anomalous" as deviation from rolling baseline, not just fixed thresholds
- [ ] Surface anomalies as new event types feeding back into the Phase A diagnosis agent
- [ ] Replace mock telemetry generation with live Redfish polling (reuse `redfish_client.py` from Phase A)
- [ ] Consider `insert_readings_batch()` once polling frequency increases
- [ ] Add a retention policy (e.g. delete rows older than N days) before the table grows unbounded

---

## 🔗 References

- [SQLite documentation](https://www.sqlite.org/docs.html)
- [Python `sqlite3` module docs](https://docs.python.org/3/library/sqlite3.html)
- [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
- [Python `contextlib.contextmanager`](https://docs.python.org/3/library/contextlib.html#contextlib.contextmanager)
- [SQLite `CREATE INDEX` docs](https://www.sqlite.org/lang_createindex.html)
- [Redfish `Status.Health` semantics — DMTF](https://www.dmtf.org/standards/redfish)

---

*Session logged: 2026-06-17 | Amritapuri, Kerala*
*Project: ai-openBMC internship contribution — Phase B Week 1*