from telemetry.database import get_connection, init_db, insert_reading

def test_database_insert_and_fetch():
    # Make sure DB is initialised
    init_db()
    
    with get_connection() as conn:
        conn.execute("DELETE FROM telemetry")
        
    row_id = insert_reading("2026-06-25T12:00:00Z", "CPU_TEMP", 72.5, "OK")
    assert row_id is not None
    
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM telemetry WHERE id = ?", (row_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["sensor"] == "CPU_TEMP"
        assert row["value"] == 72.5
        assert row["status"] == "OK"
