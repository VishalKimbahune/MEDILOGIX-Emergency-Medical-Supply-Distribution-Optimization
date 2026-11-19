"""
CLI Utility: Fetch & Cache Pune / Pimpri-Chinchwad OpenStreetMap Road Network.

Usage (from repository root):
    backend\\.venv\\Scripts\\python.exe data\\fetch_osm_network.py [--force]

Downloads drivable arterial/collector streets from Overpass API once, converts
them into a directed NetworkX street graph preserving road geometry, one-way
rules, and vehicle access restrictions, and caches the result under:
    data/processed/pune_osm_road_graph.json

Data Attribution: © OpenStreetMap contributors (ODbL 1.0).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from app.database.connection import SessionLocal  # noqa: E402
from app.services.road_network_service import sync_osm_road_network  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and cache Pune OSM road network.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download from Overpass API even if local cache exists.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        result = sync_osm_road_network(db, force_refresh=args.force)

    print("MEDILOGIX Phase 5A — OSM Road Network Sync Report")
    print("=" * 55)
    print(f"  Action          : {result.get('sync_action')}")
    print(f"  OSM Available   : {result.get('osm_available')}")
    print(f"  Active Source   : {result.get('active_source')}")
    print(f"  Cache File      : {result.get('cache_file')}")
    print(f"  Attribution     : {result.get('attribution')}")
    print(f"  Nodes / Edges   : {result.get('node_count')} / {result.get('edge_count')}")
    print(f"  One-way Edges   : {result.get('oneway_edge_count')}")
    print(f"  Main SCC Nodes  : {result.get('largest_scc_node_count')}")
    if result.get("sync_error"):
        print(f"  Sync Warning    : {result.get('sync_error')}")

    mappings = result.get("facility_mappings", [])
    if mappings:
        print(f"\nFacility Snapping ({len(mappings)} active facilities):")
        for m in mappings:
            status = "CONNECTED" if m["is_connected"] else f"DISCONNECTED ({m['disconnected_reason']})"
            print(
                f"  - {m['facility_code']:8s} ({m['facility_type']:9s}): "
                f"node={m['osm_node_id']} snap={m['snap_distance_km']} km [{status}]"
            )


if __name__ == "__main__":
    main()
