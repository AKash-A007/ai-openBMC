import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from telemetry.database import init_db
from telemetry.collector import run_forever

if __name__ == "__main__":
    print("[Collector Service] Starting...")
    init_db()
    interval = int(os.getenv("POLL_INTERVAL", "5"))
    run_forever(interval=interval)
