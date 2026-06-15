#this is the file so that we can run the entire pipeline together 
"""
main.py  —  Orchestrator
Run this to execute the full pipeline:
  1. (Optional) Fetch live Redfish data from OpenBMC
  2. Build RAG index from knowledge base
  3. Parse events from saved JSON files
  4. Diagnose each event with RAG + LLM
  5. Print results
"""

import json
from pathlib import Path
from rag_engine import build_index
from parser import extract_all_events
from agent import diagnose


def run_pipeline(fetch_live: bool = False) -> None:

    # ── Step 1: Optionally fetch live Redfish data ─────────────────────────────
    if fetch_live:
        print("=" * 50)
        print("STEP 1: Fetching live Redfish data from OpenBMC")
        print("=" * 50)
        from redfish_client import fetch_all
        fetch_all()
    else:
        print("[Main] Using saved JSON files from ./redfish_data/")

    # ── Step 2: Build RAG index ────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("STEP 2: Building RAG index")
    print("=" * 50)
    build_index()   # skips automatically if already built

    # ── Step 3: Extract events from saved JSON files ───────────────────────────
    print("\n" + "=" * 50)
    print("STEP 3: Extracting events from saved JSON files")
    print("=" * 50)
    events = extract_all_events()

    if not events:
        print("[Main] No events to diagnose. Exiting.")
        return

    # ── Step 4: Diagnose each event ────────────────────────────────────────────
    print("\n" + "=" * 50)
    print(f"STEP 4: Diagnosing {len(events)} event(s)")
    print("=" * 50)

    results = []
    for i, event in enumerate(events, 1):
        print(f"\n[{i}/{len(events)}] {event['sensor']} — {event['event']}")
        result = diagnose(event)
        results.append(result)
        print(json.dumps(result, indent=2))

    # ── Step 5: Save results ───────────────────────────────────────────────────
    output_path = Path("./diagnosis_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[Main] Results saved → {output_path}")


if __name__ == "__main__":
    # fetch_live=False  → use saved JSON files (current phase)
    # fetch_live=True   → hit live OpenBMC Redfish endpoints first
    run_pipeline(fetch_live=False)