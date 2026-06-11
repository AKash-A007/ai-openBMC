"""
redfish_client.py

Phase A - Week 1
Goal:
OpenBMC -> Redfish -> Python -> JSON
"""

import requests
import urllib3
import json

# Suppress SSL warnings from self-signed OpenBMC certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://localhost:2443"

USERNAME = "root"
PASSWORD = "0penBmc"


def get_redfish(path):
    """
    Generic helper for Redfish requests
    """

    url = f"{BASE_URL}{path}"

    try:
        response = requests.get(
            url,
            auth=(USERNAME, PASSWORD),
            verify=False,
            timeout=10,
        )

        print(f"\nRequest: {path}")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            return response.json()

        return {
            "error": response.status_code,
            "message": response.text,
        }

    except Exception as e:
        return {
            "error": str(e)
        }


def get_service_root():
    return get_redfish("/redfish/v1")

def get_system():
    return get_redfish("/redfish/v1/Systems/system")

def get_memory():
    return get_redfish("/redfish/v1/Systems/system/Memory")
def get_processors():
    return get_redfish("/redfish/v1/Systems/system/Processors")
def get_chassis():
    return get_redfish("/redfish/v1/Chassis/chassis")


def get_thermal():
    return get_redfish("/redfish/v1/Chassis/chassis/Thermal")

def get_power():
    return get_redfish("/redfish/v1/Chassis/chassis/Power")

def save_json(filename, data):

    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

    print(f"Saved: {filename}")

if __name__ == "__main__":

    service_root = get_service_root()
    system = get_system()
    memory = get_memory()
    processors = get_processors()
    chassis = get_chassis()
    thermal = get_thermal()
    power = get_power()
    print(json.dumps(service_root, indent=2))

    print(json.dumps(system, indent=2))

    print(json.dumps(memory, indent=2))

    print(json.dumps(processors, indent=2))

    print(json.dumps(chassis, indent=2))

    print(json.dumps(thermal, indent=2))

    print(json.dumps(power, indent=2))

    # Save outputs for future RAG work
    save_json("service_root.json", service_root)
    save_json("system.json", system)
    save_json("memory.json", memory)
    save_json("processors.json", processors)
    save_json("chassis.json", chassis)
    save_json("thermal.json", thermal)
    save_json("power.json", power)