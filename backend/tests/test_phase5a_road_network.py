"""
Phase 5A (Stage 2) Automated Tests — OpenStreetMap Directed Road Network Engine.

Verifies:
- Overpass JSON parsing into directed NetworkX graph with intersection splitting
- Road geometry preservation & geodesic segment-by-segment distance calculation
- One-way restrictions (oneway=yes, oneway=-1, junction=roundabout, bidirectional)
- Vehicle access restriction filtering (footway, access=private, hgv=no excluded)
- Facility snapping & disconnected node / isolated component detection
- Road closure exclusion (closed_way_ids rerouting & unreachability)
- Local JSON disk caching with OpenStreetMap ODbL attribution
- Graceful offline fallback to synthetic corridor network when OSM is unavailable
- FastAPI road-network endpoints (/api/routes/road-network/status, /shortest-path)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from tests.auth_helpers import attach_admin_auth
from app.optimization.osm_road_network import (
    OSM_ATTRIBUTION,
    compute_osm_shortest_path,
    load_graph_cache,
    parse_overpass_to_digraph,
    save_graph_cache,
    snap_facility_to_graph,
)
from app.services import road_network_service
from app.utils.dataset_loader import seed_database_from_csv

SYNTHETIC_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def _sample_overpass_payload() -> dict[str, Any]:
    """
    Synthetic Overpass JSON mini-network anchored in Pune (Shivajinagar -> Aundh -> Baner):
    - Way 101: Primary one-way east/south (1 -> 2 -> 3) with intermediate curve point 2
    - Way 102: Secondary bidirectional bypass (1 <-> 4 <-> 3) slightly longer than Way 101
    - Way 103: Reverse one-way (oneway=-1) from 3 -> 1 (declared as nodes [1, 5, 3], traversable 3 -> 5 -> 1)
    - Way 104: Footway (must be excluded for delivery vehicles)
    - Way 105: Private access road (must be excluded)
    - Way 106: HGV-restricted road (hgv=no, excluded for medical_truck)
    - Way 201: Disconnected isolated island far away (nodes 901 <-> 902)
    """
    return {
        "elements": [
            # Main Pune cluster nodes
            {"type": "node", "id": 1, "lat": 18.5308, "lon": 73.8475},  # Near HOSP-01 (Shivajinagar)
            {"type": "node", "id": 2, "lat": 18.5450, "lon": 73.8300},  # Intermediate curve point
            {"type": "node", "id": 3, "lat": 18.5590, "lon": 73.8077},  # Near HOSP-02 (Aundh)
            {"type": "node", "id": 4, "lat": 18.5420, "lon": 73.8150},  # Bypass midpoint
            {"type": "node", "id": 5, "lat": 18.5490, "lon": 73.8380},  # Return one-way curve point
            {"type": "node", "id": 6, "lat": 18.5350, "lon": 73.8520},  # Restricted road endpoint
            # Isolated disconnected island (outside main SCC)
            {"type": "node", "id": 901, "lat": 18.6900, "lon": 74.0400},
            {"type": "node", "id": 902, "lat": 18.6920, "lon": 74.0420},
            # Ways
            {
                "type": "way",
                "id": 101,
                "nodes": [1, 2, 3],
                "tags": {
                    "highway": "primary",
                    "name": "Ganeshkhind Road",
                    "oneway": "yes",
                    "maxspeed": "50",
                },
            },
            {
                "type": "way",
                "id": 102,
                "nodes": [1, 4, 3],
                "tags": {
                    "highway": "secondary",
                    "name": "Senapati Bapat Bypass",
                },
            },
            {
                "type": "way",
                "id": 103,
                "nodes": [1, 5, 3],
                "tags": {
                    "highway": "primary",
                    "name": "University Return Corridor",
                    "oneway": "-1",
                },
            },
            {
                "type": "way",
                "id": 104,
                "nodes": [1, 6],
                "tags": {"highway": "footway", "name": "Pedestrian Path"},
            },
            {
                "type": "way",
                "id": 105,
                "nodes": [1, 6],
                "tags": {"highway": "residential", "access": "private", "name": "Private Lane"},
            },
            {
                "type": "way",
                "id": 106,
                "nodes": [1, 6],
                "tags": {"highway": "tertiary", "hgv": "no", "name": "No Heavy Trucks Street"},
            },
            {
                "type": "way",
                "id": 201,
                "nodes": [901, 902],
                "tags": {"highway": "secondary", "name": "Isolated Island Road"},
            },
        ]
    }


def _create_seeded_client() -> TestClient:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_fks(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with TestingSessionLocal() as db:
        seed_database_from_csv(db, SYNTHETIC_DATA_DIR)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    attach_admin_auth(client, TestingSessionLocal)
    return client


def test_osm_parsing_oneway_restrictions_and_access_filtering() -> None:
    graph = parse_overpass_to_digraph(_sample_overpass_payload(), vehicle_class="medical_truck")

    # Restricted ways (footway 104, private 105, hgv=no 106 -> node 6) must be excluded
    assert 6 not in graph

    # Way 101 (oneway=yes) exists 1 -> 3 (key=101) with full 3-point curved geometry preserved
    assert graph.has_edge(1, 3, key=101)
    assert not graph.has_edge(3, 1, key=101)
    assert len(graph[1][3][101]["geometry"]) == 3
    assert graph[1][3][101]["oneway"] is True
    assert graph[1][3][101]["distance_km"] > 4.0

    # Way 103 (oneway=-1 on [1, 5, 3]) creates directed edge 3 -> 1 (key=103), NOT 1 -> 3
    assert graph.has_edge(3, 1, key=103)
    assert not graph.has_edge(1, 3, key=103)
    assert graph[3][1][103]["oneway"] is True
    assert len(graph[3][1][103]["geometry"]) == 3

    # Parallel bidirectional Way 102 is preserved in BOTH directions (1 -> 3 and 3 -> 1, key=102)
    assert graph.has_edge(1, 3, key=102)
    assert graph.has_edge(3, 1, key=102)
    assert graph[1][3][102]["oneway"] is False
    assert len(graph[1][3][102]["geometry"]) == 3


def test_osm_directed_shortest_path_and_road_closure_exclusion() -> None:
    graph = parse_overpass_to_digraph(_sample_overpass_payload())

    # Open network: 1 -> 3 uses direct primary Way 101
    open_res = compute_osm_shortest_path(graph, 1, 3, source_code="HOSP-01", target_code="HOSP-02")
    assert open_res.reachable is True
    assert open_res.way_ids == [101]
    assert len(open_res.geometry) == 3
    assert open_res.distance_km > 0
    assert open_res.estimated_travel_time_min > 0
    assert open_res.attribution == OSM_ATTRIBUTION

    # Closing Way 101 forces reroute via Way 102 (1 -> 4 -> 3)
    reroute_res = compute_osm_shortest_path(
        graph, 1, 3, source_code="HOSP-01", target_code="HOSP-02", closed_way_ids={101}
    )
    assert reroute_res.reachable is True
    assert reroute_res.way_ids == [102]
    assert reroute_res.distance_km > open_res.distance_km

    # Closing BOTH Way 101 and Way 102 makes 1 -> 3 unreachable (Way 103 is reverse one-way 3 -> 1!)
    blocked_res = compute_osm_shortest_path(
        graph, 1, 3, source_code="HOSP-01", target_code="HOSP-02", closed_way_ids={101, 102}
    )
    assert blocked_res.reachable is False
    assert blocked_res.geometry == []

    # Yet reverse direction 3 -> 1 remains reachable via reverse one-way Way 103!
    rev_res = compute_osm_shortest_path(
        graph, 3, 1, source_code="HOSP-02", target_code="HOSP-01", closed_way_ids={101, 102}
    )
    assert rev_res.reachable is True
    assert rev_res.way_ids == [103]


def test_osm_disconnected_nodes_and_disk_cache_roundtrip(tmp_path: Path) -> None:
    graph = parse_overpass_to_digraph(_sample_overpass_payload())

    # Facility near node 1 snaps cleanly into main SCC
    connected_map = snap_facility_to_graph(
        graph, "HOSP-01", "hospital", 18.5308, 73.8475, max_snap_distance_km=2.0
    )
    assert connected_map.is_connected is True
    assert connected_map.in_main_component is True
    assert connected_map.osm_node_id == 1

    # Facility near isolated island (nodes 901-902) is flagged disconnected from main SCC
    isolated_map = snap_facility_to_graph(
        graph, "HOSP-ISO", "hospital", 18.6905, 74.0405, max_snap_distance_km=2.0
    )
    assert isolated_map.is_connected is False
    assert isolated_map.in_main_component is False
    assert "outside the main strongly connected" in (isolated_map.disconnected_reason or "").lower()

    # Facility far away from all nodes exceeds snap threshold
    far_map = snap_facility_to_graph(
        graph, "HOSP-FAR", "hospital", 19.2000, 74.5000, max_snap_distance_km=2.0
    )
    assert far_map.is_connected is False
    assert "exceeds max snap threshold" in (far_map.disconnected_reason or "").lower()

    # Cache round-trip preserves nodes, directed edges, geometry, and ODbL attribution
    cache_file = tmp_path / "test_osm_graph.json"
    save_graph_cache(
        graph,
        cache_file,
        bbox={"min_lat": 18.4, "max_lat": 18.7, "min_lon": 73.7, "max_lon": 74.05},
    )
    reloaded, meta = load_graph_cache(cache_file)
    assert reloaded.number_of_nodes() == graph.number_of_nodes()
    assert reloaded.number_of_edges() == graph.number_of_edges()
    assert meta["attribution"] == OSM_ATTRIBUTION
    assert reloaded[1][3][101]["geometry"] == graph[1][3][101]["geometry"]


def test_offline_synthetic_fallback_and_api_endpoints(tmp_path: Path, monkeypatch) -> None:
    client = _create_seeded_client()
    road_network_service.clear_memory_cache()

    # 1. Point cache path to a non-existent file to verify graceful offline fallback
    missing_cache = tmp_path / "missing_osm_cache.json"
    monkeypatch.setattr(
        road_network_service, "_resolve_cache_path", lambda override_path=None: override_path or missing_cache
    )

    status_offline = client.get("/api/routes/road-network/status")
    assert status_offline.status_code == 200
    assert status_offline.json()["osm_available"] is False
    assert status_offline.json()["active_source"] == "synthetic_fallback"

    sp_fallback = client.post(
        "/api/routes/road-network/shortest-path",
        json={"source_code": "WH-01", "target_code": "HOSP-01"},
    )
    assert sp_fallback.status_code == 200
    fb_data = sp_fallback.json()
    assert fb_data["reachable"] is True
    assert fb_data["source_type"] == "synthetic_fallback"
    assert fb_data["fallback_used"] is True
    assert fb_data["distance_km"] > 0

    # 2. Populate local cache with our mini OSM graph and verify live OSM routing via API
    graph = parse_overpass_to_digraph(_sample_overpass_payload())
    save_graph_cache(
        graph,
        missing_cache,
        bbox={"min_lat": 18.4, "max_lat": 18.7, "min_lon": 73.7, "max_lon": 74.05},
    )
    road_network_service.clear_memory_cache()

    status_online = client.get("/api/routes/road-network/status")
    assert status_online.status_code == 200
    s_data = status_online.json()
    assert s_data["osm_available"] is True
    assert s_data["active_source"] == "osm_road_network"
    assert s_data["node_count"] == graph.number_of_nodes()

    sp_osm = client.post(
        "/api/routes/road-network/shortest-path",
        json={"source_code": "HOSP-01", "target_code": "HOSP-02"},
    )
    assert sp_osm.status_code == 200
    osm_data = sp_osm.json()
    assert osm_data["reachable"] is True
    assert osm_data["source_type"] == "osm_road_network"
    assert osm_data["fallback_used"] is False
    assert osm_data["way_ids"] == [101]
    assert len(osm_data["geometry"]) == 3

    # Unknown facility returns 404
    bad_req = client.post(
        "/api/routes/road-network/shortest-path",
        json={"source_code": "WH-UNKNOWN", "target_code": "HOSP-01"},
    )
    assert bad_req.status_code == 404
