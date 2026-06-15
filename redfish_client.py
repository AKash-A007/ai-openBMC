"""
redfish_client.py  —  Phase A Week 1
OpenBMC → Redfish → Python → JSON
"""

import requests
import urllib3
import json
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL  = "https://localhost:2443"
USERNAME  = "root"
PASSWORD  = "0penBmc"
DATA_DIR  = Path("./redfish_data")   # ← all saves go here


def get_redfish(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    try:
        response = requests.get(url, auth=(USERNAME, PASSWORD),
                                verify=False, timeout=10)
        print(f"  GET {path}  →  {response.status_code}")
        return response.json() if response.status_code == 200 else {
            "error": response.status_code, "message": response.text
        }
    except Exception as e:
        return {"error": str(e)}


def save_json(filename: str, data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"  Saved → {path}")


def fetch_all() -> None:
    """Fetch all Redfish endpoints and save to redfish_data/."""
    print("\n[Redfish] Fetching all endpoints...")
    endpoints = {
        "service_root.json" : "/redfish/v1",
        "system.json"       : "/redfish/v1/Systems/system",
        "memory.json"       : "/redfish/v1/Systems/system/Memory",
        "processors.json"   : "/redfish/v1/Systems/system/Processors",
        "chassis.json"      : "/redfish/v1/Chassis/chassis",
        "thermal.json"      : "/redfish/v1/Chassis/chassis/Thermal",
        "power.json"        : "/redfish/v1/Chassis/chassis/Power",
    }
    for filename, path in endpoints.items():
        data = get_redfish(path)
        save_json(filename, data)
    print("[Redfish] Done.\n")


if __name__ == "__main__":
    fetch_all()