import time
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telemetry.database import init_db
from telemetry.query import get_sensor_history, get_sensor_history_full
from rag_engine import build_index, rag_query
from agent import diagnose

def benchmark_telemetry():
    print("=== Telemetry Query Benchmark ===")
    start = time.time()
    for _ in range(100):
        get_sensor_history("CPU_TEMP", limit=50)
    dur = time.time() - start
    print(f"100 raw history calls: {dur:.4f} seconds ({dur/100:.6f} s/call)")

    start = time.time()
    for _ in range(100):
        get_sensor_history_full("CPU_TEMP", limit=50)
    dur = time.time() - start
    print(f"100 full history calls: {dur:.4f} seconds ({dur/100:.6f} s/call)")
    print()

def benchmark_rag():
    print("=== RAG Search Latency & Caching Benchmark ===")
    query = "Memory ECC error"
    
    # Ensure RAG model is built
    build_index()
    
    # Cache Miss
    start = time.time()
    rag_query(query, n_chunks=1)
    dur_miss = time.time() - start
    print(f"RAG query (Cache MISS): {dur_miss:.4f} seconds")

    # Cache Hit
    start = time.time()
    rag_query(query, n_chunks=1)
    dur_hit = time.time() - start
    print(f"RAG query (Cache HIT): {dur_hit:.6f} seconds")
    print(f"Speedup: {dur_miss / (dur_hit or 1e-6):.2f}x")
    print()

def benchmark_diagnosis():
    print("=== Mock LLM Diagnosis Benchmark ===")
    event = {"sensor": "DIMM_B2", "event": "Memory ECC Error", "severity": "WARNING"}
    start = time.time()
    diagnose(event)
    dur = time.time() - start
    print(f"Diagnosis runtime: {dur:.4f} seconds")
    print()

if __name__ == "__main__":
    init_db()
    
    # Populate some dummy telemetry data for testing database fetch speed
    from telemetry.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM telemetry")
        
    from telemetry.database import insert_reading
    for i in range(100):
        insert_reading("2026-06-25T12:00:00Z", "CPU_TEMP", 70.0 + (i % 10), "OK")
    
    benchmark_telemetry()
    benchmark_rag()
    benchmark_diagnosis()
    print("Benchmark run complete!")
