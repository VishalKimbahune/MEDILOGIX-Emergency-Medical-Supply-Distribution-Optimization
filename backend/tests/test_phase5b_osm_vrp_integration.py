"""
Phase 5 Stage 3 Deterministic Test Suite:
OSM Road Network Integration with Google OR-Tools CVRP, Dispatch Persistence,
Road Closures, Fallback Handling, and Isolated Scenario Simulation.

All tests use deterministic mocked/in-memory OSM MultiDiGraphs and temporary
cache files — zero dependence on live Overpass API availability.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.connection import get_db
from app.database.migrations import ensure_additive_columns
from app.main import app
from tests.auth_helpers import attach_admin_auth
from app.models.dispatch import VehicleAssignment
from app.optimization.osm_road_network import (
    OSM_ATTRIBUTION,
    build_osm_distance_time_matrix,
    save_graph_cache,
)
from app.optimization.vehicle_routing import (
    DepotRoutingInput,
    ShipmentLineInput,
    VRPStopInput,
    VRPVehicleInput,
    solve_depot_vrp,
    solve_multi_depot_vrp,
)
from app.services import dispatch_service, road_network_service
from app.utils.dataset_loader import seed_database_from_csv

SYNTHETIC_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def _add_road_edge(
    graph: nx.MultiDiGraph,
    u: int,
    v: int,
    *,
    way_id: int,
    name: str,
    distance_km: float,
    time_min: float,
    geom: list[list[float]],
    oneway: bool = False,
    highway: str = "primary",
    vehicle_accessible: bool = True,
    hgv_restricted: bool = False,
) -> None:
    attrs = {
        "osm_way_id": way_id,
        "name": name,
        "highway": highway,
        "oneway": oneway,
        "direction_rule": "forward" if oneway else "both",
        "distance_km": distance_km,
        "estimated_travel_time_min": time_min,
        "vehicle_accessible": vehicle_accessible,
        "hgv_restricted": hgv_restricted,
        "geometry": geom,
    }
    graph.add_edge(u, v, key=way_id, **attrs)
    if not oneway:
        rev_attrs = dict(attrs)
        rev_attrs["geometry"] = list(reversed(geom))
        graph.add_edge(v, u, key=way_id, **rev_attrs)


def _build_mock_pune_osm_graph() -> nx.MultiDiGraph:
    """
    Build a rich deterministic directed OSM MultiDiGraph covering all 3 synthetic
    warehouses (WH-01..WH-03) and all 8 synthetic hospitals (HOSP-01..HOSP-08)
    with realistic curved intermediate coordinates, distinct way IDs, parallel
    fast-vs-short corridors, one-way segments, and HGV-restricted shortcuts.
    """
    coords: dict[int, tuple[float, float]] = {
        # Warehouses
        1: (18.6298, 73.7997),   # WH-01 Pimpri
        2: (18.5018, 73.8636),   # WH-02 Swargate
        3: (18.5808, 73.9787),   # WH-03 Wagholi
        # Hospitals (matching data/synthetic/hospitals.csv exact coordinates)
        11: (18.5308, 73.8475),  # HOSP-01 Shivajinagar
        12: (18.5590, 73.8077),  # HOSP-02 Aundh
        13: (18.5590, 73.7868),  # HOSP-03 Baner
        14: (18.5074, 73.8077),  # HOSP-04 Kothrud
        15: (18.4695, 73.8890),  # HOSP-05 Kondhwa
        16: (18.5089, 73.9260),  # HOSP-06 Hadapsar
        17: (18.6210, 73.8080),  # HOSP-07 Pimpri-Chinchwad
        18: (18.5045, 73.8585),  # HOSP-08 Swargate
        # Central junction hub
        100: (18.5450, 73.8600),
    }

    g = nx.MultiDiGraph()
    for nid, (lat, lon) in coords.items():
        g.add_node(nid, lat=lat, lon=lon)

    def _curved_geom(u: int, v: int, bend: float = 0.004) -> list[list[float]]:
        la1, lo1 = coords[u]
        la2, lo2 = coords[v]
        mid = [round((la1 + la2) / 2.0 + bend, 6), round((lo1 + lo2) / 2.0 - bend, 6)]
        return [[la1, lo1], mid, [la2, lo2]]

    # Parallel short-but-slow vs longer-but-fast ways between WH-01 (1) and HOSP-02 (12)
    _add_road_edge(
        g, 1, 12, way_id=9001, name="Pimpri Inner Arterial (Short/Slow)",
        distance_km=8.0, time_min=34.0, geom=_curved_geom(1, 12, 0.002), highway="tertiary",
    )
    _add_road_edge(
        g, 1, 12, way_id=9002, name="PCMC Expressway Bypass (Longer/Fast)",
        distance_km=11.5, time_min=14.0, geom=_curved_geom(1, 12, -0.006), highway="motorway",
    )

    # HGV-restricted shortcut (blocked for medical_truck) between WH-01 (1) and HOSP-01 (11)
    _add_road_edge(
        g, 1, 11, way_id=9003, name="Old Bridge (HGV No)",
        distance_km=4.0, time_min=7.0, geom=_curved_geom(1, 11, 0.001), hgv_restricted=True,
    )
    # Legal arterial between WH-01 (1) and HOSP-01 (11)
    _add_road_edge(
        g, 1, 11, way_id=9004, name="Old Pune-Mumbai Highway",
        distance_km=13.5, time_min=24.0, geom=_curved_geom(1, 11, -0.004), highway="trunk",
    )
    # Parallel backup bypass for WH-01 -> HOSP-01 (so closing 9004 still allows reroute!)
    _add_road_edge(
        g, 1, 11, way_id=9005, name="Aundh-Khadki Detour Road",
        distance_km=16.2, time_min=30.0, geom=_curved_geom(1, 11, 0.007), highway="secondary",
    )

    # Connect remaining facilities into a rich strongly connected Pune network
    links = [
        (1, 17, 9010, "Pimpri Main Link", 1.8, 4.5),
        (17, 12, 9011, "Wakad-Baner Link", 8.2, 16.0),
        (12, 14, 9012, "Baner-Hinjewadi Road", 7.4, 15.0),
        (14, 1, 9013, "Hinjewadi-Pimpri Spine", 9.6, 19.0),
        (12, 13, 9014, "Pashan-Kothrud Road", 6.8, 14.0),
        (13, 11, 9015, "Karve Road", 5.9, 13.0),
        (11, 100, 9016, "JM-Bund Garden Link", 3.1, 7.0),
        (100, 2, 9017, "Swargate Central Corridor", 5.2, 11.5),
        (2, 13, 9018, "Swargate-Kothrud Road", 6.4, 14.0),
        (2, 15, 9019, "Bibwewadi-Kondhwa Road", 5.6, 12.5),
        (15, 16, 9020, "Kondhwa-Hadapsar Bypass", 6.9, 15.0),
        (2, 16, 9021, "Solapur Highway", 7.8, 16.0),
        (16, 18, 9022, "Magarpatta-Kharadi Road", 8.5, 17.5),
        (18, 3, 9023, "Nagar Road Wagholi", 7.2, 14.0),
        (3, 16, 9024, "Wagholi-Hadapsar Eastern Ring", 10.4, 20.5),
        (18, 100, 9025, "Airport-Bund Garden Road", 7.1, 15.0),
        (11, 18, 9026, "Yerawada Arterial", 8.8, 18.0),
        (2, 11, 9027, "Bajirao-Shivajinagar Road", 4.7, 11.0),
    ]
    for u, v, wid, rname, d_km, t_min in links:
        _add_road_edge(
            g, u, v, way_id=wid, name=rname, distance_km=d_km, time_min=t_min, geom=_curved_geom(u, v)
        )

    return g


def _create_seeded_client(osm_cache_path: Path | None = None) -> tuple[TestClient, Any]:
    """Create isolated in-memory SQLite DB seeded with synthetic CSVs + FK enforcement."""
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
    return client, TestingSessionLocal


# =============================================================================
# 1–7. OSM MATRIX, OBJECTIVES, ONE-WAY, VEHICLE ACCESS, CLOSURES & UNREACHABLE
# =============================================================================


def test_osm_distance_vs_travel_time_matrices_and_objectives() -> None:
    """
    Verify:
    - OSM distance matrix construction (min_distance picks shorter 8.0 km way 9001).
    - OSM travel-time matrix construction (min_time picks faster 14.0 min motorway way 9002).
    - OR-Tools selects OSM-based routes and reports BOTH total distance and estimated time.
    """
    graph = _build_mock_pune_osm_graph()
    facilities = [
        {"code": "WH-01", "type": "warehouse", "lat": 18.6298, "lon": 73.7997},
        {"code": "HOSP-02", "type": "hospital", "lat": 18.5590, "lon": 73.8077},
    ]

    dist_matrix = build_osm_distance_time_matrix(graph, facilities, weight_metric="distance_km")
    time_matrix = build_osm_distance_time_matrix(
        graph, facilities, weight_metric="estimated_travel_time_min"
    )

    # Matrix verification
    leg_dist = dist_matrix.legs[("WH-01", "HOSP-02")]
    leg_time = time_matrix.legs[("WH-01", "HOSP-02")]
    assert leg_dist.reachable and leg_time.reachable
    assert leg_dist.way_ids == [9001]
    assert leg_dist.distance_km == 8.0
    assert leg_time.way_ids == [9002]
    assert leg_time.estimated_travel_time_min == 14.0
    assert leg_time.distance_km == 11.5  # Longer in km, faster in time!

    def _make_depot(objective: str, matrix: Any) -> DepotRoutingInput:
        return DepotRoutingInput(
            warehouse_id=1,
            warehouse_code="WH-01",
            warehouse_name="Pimpri Hub",
            area="Pimpri",
            latitude=18.6298,
            longitude=73.7997,
            vehicles=[VRPVehicleInput(1, "VEH-01", "medical_truck", 2500.0, "available")],
            stops=[
                VRPStopInput(
                    hospital_id=2,
                    hospital_code="HOSP-02",
                    hospital_name="Aundh Hospital",
                    area="Aundh",
                    priority_level="high",
                    latitude=18.5590,
                    longitude=73.8077,
                    shipment_lines=[ShipmentLineInput(1, "PROD-01", "O2", "cyl", 30.0, 18.5)],
                )
            ],
            routing_objective=objective,  # type: ignore[arg-type]
            routing_source="osm",
            osm_legs=matrix.legs,
            attribution=OSM_ATTRIBUTION,
        )

    res_dist = solve_depot_vrp(_make_depot("min_distance", dist_matrix))
    res_time = solve_depot_vrp(_make_depot("min_time", time_matrix))

    assert res_dist.status == "Optimal" and res_time.status == "Optimal"
    assert res_dist.routing_source == "osm" and res_dist.routing_objective == "min_distance"
    assert res_time.routing_source == "osm" and res_time.routing_objective == "min_time"

    # Distance-optimal tour is shorter (16.0 km) but slower (68.0 min)
    assert res_dist.total_distance_km < res_time.total_distance_km
    assert res_dist.total_duration_min > res_time.total_duration_min
    assert 9001 in res_dist.routes[0].osm_way_ids
    assert 9002 in res_time.routes[0].osm_way_ids
    # Both routes carry real curved OSM geometry (> 3 straight-line points)
    assert len(res_dist.routes[0].route_geometry) > 3
    assert len(res_time.routes[0].route_geometry) > 3


def test_oneway_restrictions_and_vehicle_access_enforcement() -> None:
    """
    Verify:
    - One-way edges force asymmetric outbound vs return paths in OSM matrix & OR-Tools.
    - HGV-restricted (`hgv_restricted=True`) and `vehicle_accessible=False` edges are never used.
    """
    g = nx.MultiDiGraph()
    g.add_node(1, lat=18.6000, lon=73.8000)  # WH-01
    g.add_node(2, lat=18.5600, lon=73.8400)  # HOSP-01
    g.add_node(3, lat=18.5800, lon=73.8600)  # Detour junction

    # Direct 1 -> 2 is ONE-WAY forward only (5 km)
    _add_road_edge(
        g, 1, 2, way_id=501, name="One-Way Direct Ave",
        distance_km=5.0, time_min=10.0,
        geom=[[18.6000, 73.8000], [18.5800, 73.8200], [18.5600, 73.8400]],
        oneway=True,
    )
    # Restricted return 2 -> 1 (hgv_restricted=True) — must be rejected for medical_truck!
    _add_road_edge(
        g, 2, 1, way_id=502, name="Low Clearance Bridge (HGV No)",
        distance_km=4.5, time_min=9.0,
        geom=[[18.5600, 73.8400], [18.6000, 73.8000]],
        oneway=True, hgv_restricted=True,
    )
    # Inaccessible pedestrian/private shortcut 2 -> 1
    _add_road_edge(
        g, 2, 1, way_id=503, name="Private Alley",
        distance_km=4.0, time_min=8.0,
        geom=[[18.5600, 73.8400], [18.6000, 73.8000]],
        oneway=True, vehicle_accessible=False,
    )
    # Legal one-way return loop: 2 -> 3 -> 1 (11 km total)
    _add_road_edge(
        g, 2, 3, way_id=504, name="East Ring Northbound",
        distance_km=6.0, time_min=12.0,
        geom=[[18.5600, 73.8400], [18.5800, 73.8600]],
        oneway=True,
    )
    _add_road_edge(
        g, 3, 1, way_id=505, name="Ring Return Westbound",
        distance_km=5.0, time_min=10.0,
        geom=[[18.5800, 73.8600], [18.6000, 73.8000]],
        oneway=True,
    )

    facilities = [
        {"code": "WH-01", "type": "warehouse", "lat": 18.6000, "lon": 73.8000},
        {"code": "HOSP-01", "type": "hospital", "lat": 18.5600, "lon": 73.8400},
    ]
    matrix = build_osm_distance_time_matrix(g, facilities, vehicle_type="medical_truck")

    out_leg = matrix.legs[("WH-01", "HOSP-01")]
    ret_leg = matrix.legs[("HOSP-01", "WH-01")]
    assert out_leg.reachable and ret_leg.reachable
    assert out_leg.distance_km == 5.0
    assert ret_leg.distance_km == 11.0  # Asymmetric one-way return!
    assert 502 not in ret_leg.way_ids
    assert 503 not in ret_leg.way_ids
    assert ret_leg.way_ids == [504, 505]

    depot = DepotRoutingInput(
        warehouse_id=1,
        warehouse_code="WH-01",
        warehouse_name="Hub",
        area="Pune",
        latitude=18.6000,
        longitude=73.8000,
        vehicles=[VRPVehicleInput(1, "VEH-01", "medical_truck", 2000.0, "available")],
        stops=[
            VRPStopInput(
                hospital_id=1,
                hospital_code="HOSP-01",
                hospital_name="Hospital 1",
                area="Pune",
                priority_level="critical",
                latitude=18.5600,
                longitude=73.8400,
                shipment_lines=[ShipmentLineInput(1, "P1", "O2", "cyl", 10.0, 18.5)],
            )
        ],
        routing_source="osm",
        osm_legs=matrix.legs,
    )
    res = solve_depot_vrp(depot)
    assert res.status == "Optimal"
    assert res.total_distance_km == 16.0  # 5.0 out + 11.0 return
    assert 502 not in res.routes[0].osm_way_ids
    assert 503 not in res.routes[0].osm_way_ids


def test_closed_osm_way_avoidance_and_unreachable_hospital_reporting() -> None:
    """
    Verify:
    - Closing an OSM way forces rerouting onto an alternate open way (closed way excluded).
    - Closing ALL open ways to a hospital marks it unreachable (NEVER silently invents a synthetic route).
    """
    graph = _build_mock_pune_osm_graph()
    facilities = [
        {"code": "WH-01", "type": "warehouse", "lat": 18.6298, "lon": 73.7997},
        {"code": "HOSP-01", "type": "hospital", "lat": 18.5308, "lon": 73.8475},
        {"code": "HOSP-02", "type": "hospital", "lat": 18.5590, "lon": 73.7868},
    ]

    # Case A: Close primary way 9004 (WH-01 -> HOSP-01); must reroute via 9005 (or open network)
    mat_reroute = build_osm_distance_time_matrix(
        graph, facilities, weight_metric="distance_km", closed_way_ids={9004}
    )
    assert mat_reroute.legs[("WH-01", "HOSP-01")].reachable is True
    assert 9004 not in mat_reroute.legs[("WH-01", "HOSP-01")].way_ids
    assert len(mat_reroute.closed_osm_ways) == 1
    assert mat_reroute.closed_osm_ways[0]["way_id"] == 9004

    # Case B: Add a completely isolated hospital outside snap distance (far away)
    facilities_with_isolated = facilities + [
        {"code": "HOSP-ISO", "type": "hospital", "lat": 19.2000, "lon": 74.9000},
    ]
    mat_iso = build_osm_distance_time_matrix(
        graph, facilities_with_isolated, weight_metric="distance_km", closed_way_ids={9004}
    )
    assert mat_iso.legs[("WH-01", "HOSP-ISO")].reachable is False
    assert any(u["facility_code"] == "HOSP-ISO" for u in mat_iso.unreachable_facilities)

    depot = DepotRoutingInput(
        warehouse_id=1,
        warehouse_code="WH-01",
        warehouse_name="Pimpri Hub",
        area="Pimpri",
        latitude=18.6298,
        longitude=73.7997,
        vehicles=[VRPVehicleInput(1, "VEH-01", "medical_truck", 3000.0, "available")],
        stops=[
            VRPStopInput(
                hospital_id=1,
                hospital_code="HOSP-01",
                hospital_name="Shivajinagar",
                area="Shivajinagar",
                priority_level="critical",
                latitude=18.5308,
                longitude=73.8475,
                shipment_lines=[ShipmentLineInput(1, "P1", "O2", "cyl", 10.0, 18.5)],
            ),
            VRPStopInput(
                hospital_id=99,
                hospital_code="HOSP-ISO",
                hospital_name="Isolated Clinic",
                area="Remote",
                priority_level="normal",
                latitude=19.2000,
                longitude=74.9000,
                shipment_lines=[ShipmentLineInput(1, "P1", "O2", "cyl", 10.0, 18.5)],
            ),
        ],
        routing_source="osm",
        osm_legs=mat_iso.legs,
        closed_way_ids=[9004],
        closed_osm_ways=mat_iso.closed_osm_ways,
    )
    res = solve_depot_vrp(depot)
    assert res.status == "Partial"
    assert res.unreachable_hospitals == ["HOSP-ISO"]
    assert any(c["to_code"] == "HOSP-ISO" for c in res.unreachable_connections)
    # Routed stops must contain ONLY HOSP-01 and NEVER use closed way 9004
    routed_codes = [s.hospital_code for r in res.routes for s in r.stops]
    assert routed_codes == ["HOSP-01"]
    assert 9004 not in res.routes[0].osm_way_ids


# =============================================================================
# 8–9. SYNTHETIC FALLBACK (MISSING CACHE & INVALID/CORRUPTED CACHE)
# =============================================================================


def test_synthetic_fallback_when_osm_cache_missing_or_invalid(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """
    Verify:
    - Missing OSM cache activates synthetic_fallback with clear fallback_warning.
    - Corrupted/invalid OSM cache JSON also activates synthetic_fallback cleanly.
    """
    client, _ = _create_seeded_client()
    opt_res = client.post("/api/optimization/priority", json={})
    assert opt_res.status_code == 200
    run_id = opt_res.json()["id"]

    # Case 1: Missing cache file
    missing_cache = tmp_path / "does_not_exist_osm.json"
    monkeypatch.setattr(
        road_network_service, "_resolve_cache_path", lambda override_path=None: override_path or missing_cache
    )
    road_network_service.clear_memory_cache()

    res_missing = client.post(
        "/api/routes/dispatch-plans",
        json={"optimization_run_id": run_id, "routing_objective": "min_distance"},
    )
    assert res_missing.status_code == 201
    plan_missing = res_missing.json()
    assert plan_missing["routing_source"] == "synthetic_fallback"
    assert plan_missing["fallback_warning"] is not None
    assert "not found" in plan_missing["fallback_warning"].lower()
    assert plan_missing["total_routes"] > 0

    # Case 2: Corrupted / invalid JSON cache file
    corrupt_cache = tmp_path / "corrupt_osm.json"
    corrupt_cache.write_text("{not-valid-json", encoding="utf-8")
    monkeypatch.setattr(
        road_network_service, "_resolve_cache_path", lambda override_path=None: override_path or corrupt_cache
    )
    road_network_service.clear_memory_cache()

    res_corrupt = client.post(
        "/api/routes/dispatch-plans",
        json={"optimization_run_id": run_id, "routing_objective": "min_time"},
    )
    assert res_corrupt.status_code == 201
    plan_corrupt = res_corrupt.json()
    assert plan_corrupt["routing_source"] == "synthetic_fallback"
    assert plan_corrupt["routing_objective"] == "min_time"
    assert plan_corrupt["fallback_warning"] is not None
    assert "invalid" in plan_corrupt["fallback_warning"].lower()

    # Case 3: Structurally invalid OSM graph (0 edges)
    empty_graph_cache = tmp_path / "empty_osm.json"
    empty_graph_cache.write_text(
        json.dumps({"metadata": {}, "nodes": [{"id": 1, "lat": 18.5, "lon": 73.8}], "edges": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        road_network_service, "_resolve_cache_path", lambda override_path=None: override_path or empty_graph_cache
    )
    road_network_service.clear_memory_cache()

    res_empty = client.post(
        "/api/routes/dispatch-plans",
        json={"optimization_run_id": run_id},
    )
    assert res_empty.status_code == 201
    assert res_empty.json()["routing_source"] == "synthetic_fallback"
    assert res_empty.json()["fallback_warning"] is not None


# =============================================================================
# 10–16. API GEOMETRY PERSISTENCE, CONSERVATION, CAPACITY, MULTI-DEPOT, SCENARIO ISOLATION & LIFECYCLE
# =============================================================================


def test_api_osm_geometry_persistence_conservation_capacity_and_lifecycle(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """
    End-to-end deterministic API verification with mocked Pune OSM cache:
    - Generates dispatch plan via OSM network (min_distance & min_time).
    - Verifies curved route_geometry, osm_way_ids, attribution, and travel-time disclaimer.
    - Verifies persistence & retrieval via GET /api/routes/dispatch-plans/{id}.
    - Verifies 100% LP-to-VRP shipment conservation, vehicle capacity, and multi-depot isolation.
    - Verifies backward compatibility for legacy VehicleAssignment with route_geometry_json=None.
    - Verifies dispatch lifecycle state machine and zero mutation of live inventory/demands.
    """
    mock_graph = _build_mock_pune_osm_graph()
    cache_file = tmp_path / "mock_pune_osm.json"
    save_graph_cache(
        mock_graph,
        cache_path=cache_file,
        bbox={"min_lat": 18.4, "max_lat": 18.7, "min_lon": 73.7, "max_lon": 74.05},
    )
    monkeypatch.setattr(
        road_network_service, "_resolve_cache_path", lambda override_path=None: override_path or cache_file
    )
    road_network_service.clear_memory_cache()

    client, SessionMaker = _create_seeded_client()
    inv_before = client.get("/api/inventory").json()
    dem_before = client.get("/api/demands").json()

    opt_res = client.post("/api/optimization/priority", json={})
    assert opt_res.status_code == 200
    opt_data = opt_res.json()
    run_id = opt_data["id"]

    # Generate OSM dispatch plan (min_time + closing way 9004)
    create_res = client.post(
        "/api/routes/dispatch-plans",
        json={
            "optimization_run_id": run_id,
            "routing_objective": "min_time",
            "closed_way_ids": [9004],
            "allow_multi_trip": True,
            "max_trips_per_vehicle": 3,
            "allow_split_deliveries": True,
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()

    assert created["routing_source"] == "osm"
    assert created["routing_objective"] == "min_time"
    assert created["solver_status"] == "Optimal"
    assert created["closed_way_ids"] == [9004]
    assert len(created["closed_osm_ways"]) == 1
    assert created["attribution"] == OSM_ATTRIBUTION
    assert "not live traffic" in created["travel_time_disclaimer"].lower()

    # Retrieve persisted plan via GET and confirm geometry & way IDs persisted identically
    fetched = client.get(f"/api/routes/dispatch-plans/{created['id']}").json()
    assert fetched["plan_code"] == created["plan_code"]
    assert fetched["routing_source"] == "osm"
    assert fetched["routing_objective"] == "min_time"
    assert len(fetched["vehicle_assignments"]) == len(created["vehicle_assignments"])

    # Verify LP-to-VRP conservation, vehicle capacity, multi-depot isolation, and closed way exclusion
    vehicles_by_code = {v["vehicle_code"]: v["warehouse_code"] for v in client.get("/api/routes/vehicles").json()}
    planned_by_triplet: dict[tuple[str, str, str], float] = defaultdict(float)

    for va in fetched["vehicle_assignments"]:
        assert va["routing_source"] == "osm"
        assert va["routing_objective"] == "min_time"
        assert len(va["route_geometry"]) >= 3
        assert len(va["osm_way_ids"]) >= 1
        assert 9004 not in va["osm_way_ids"]  # Closed OSM way strictly excluded
        assert 9003 not in va["osm_way_ids"]  # HGV-restricted way strictly excluded
        assert va["total_load_kg"] <= va["capacity_kg"] + 0.1
        # Multi-depot isolation: vehicle belongs strictly to its home warehouse
        assert vehicles_by_code[va["vehicle_code"]] == va["warehouse_code"]

        for stop in va["delivery_stops"]:
            for line in stop["shipment_lines"]:
                assert line["quantity_delivered"] == 0.0
                planned_by_triplet[
                    (va["warehouse_code"], stop["hospital_code"], line["product_code"])
                ] += float(line["quantity_planned"])

    lp_by_triplet: dict[tuple[str, str, str], float] = defaultdict(float)
    for alloc in opt_data["allocations"]:
        lp_by_triplet[
            (alloc["warehouse_code"], alloc["hospital_code"], alloc["product_code"])
        ] += float(alloc["quantity_allocated"])

    assert set(planned_by_triplet.keys()) == set(lp_by_triplet.keys())
    for key, lp_qty in lp_by_triplet.items():
        assert abs(planned_by_triplet[key] - lp_qty) <= 0.05

    # Verify dispatch lifecycle transitions still work cleanly
    assert (
        client.patch(
            f"/api/routes/dispatch-plans/{created['id']}/status", json={"status": "delivered"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/routes/dispatch-plans/{created['id']}/status", json={"status": "dispatched"}
        ).status_code
        == 200
    )

    # Verify backward-compatible retrieval of a historical row where route_geometry_json is NULL
    with SessionMaker() as db:
        first_va = db.get(VehicleAssignment, fetched["vehicle_assignments"][0]["id"])
        assert first_va is not None
        first_va.route_geometry_json = None
        db.commit()

    legacy_fetched = client.get(f"/api/routes/dispatch-plans/{created['id']}").json()
    assert len(legacy_fetched["vehicle_assignments"][0]["route_geometry"]) >= 2

    # Verify live inventory & demands untouched
    assert client.get("/api/inventory").json() == inv_before
    assert client.get("/api/demands").json() == dem_before


def test_scenario_osm_closure_isolation_and_additive_migration(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """
    Verify:
    - Scenario simulation with OSM `closed_way_ids` excludes closed ways in disrupted routes,
      returns `closed_osm_ways` and curved `route_geometry`, and NEVER mutates the live OSM
      graph cache or operational database tables.
    - Additive migration `ensure_additive_columns` safely upgrades a legacy SQLite table
      missing `route_geometry_json` without dropping existing rows.
    """
    mock_graph = _build_mock_pune_osm_graph()
    cache_file = tmp_path / "mock_pune_osm_scen.json"
    save_graph_cache(
        mock_graph,
        cache_path=cache_file,
        bbox={"min_lat": 18.4, "max_lat": 18.7, "min_lon": 73.7, "max_lon": 74.05},
    )
    cache_bytes_before = cache_file.read_bytes()

    monkeypatch.setattr(
        road_network_service, "_resolve_cache_path", lambda override_path=None: override_path or cache_file
    )
    road_network_service.clear_memory_cache()

    client, _ = _create_seeded_client()
    roads_before = client.get("/api/routes").json()
    opt_run = client.post("/api/optimization/priority", json={}).json()

    sim_res = client.post(
        "/api/scenarios/simulate",
        json={
            "baseline_run_id": opt_run["id"],
            "name": "OSM Highway Closure Isolation Test",
            "scenario_type": "road_closure",
            "closed_way_ids": [9004, 9021],
            "routing_objective": "min_distance",
        },
    )
    assert sim_res.status_code == 201
    sim_data = sim_res.json()

    assert sim_data["routing_source"] == "osm"
    assert sim_data["closed_way_ids"] == [9004, 9021]
    assert len(sim_data["closed_osm_ways"]) == 2
    assert len(sim_data["disrupted_routes"]) > 0
    for route in sim_data["disrupted_routes"]:
        assert len(route["route_geometry"]) >= 3
        assert 9004 not in route["osm_way_ids"]
        assert 9021 not in route["osm_way_ids"]

    # Confirm ZERO mutation of live roads table or cached OSM JSON file
    assert client.get("/api/routes").json() == roads_before
    assert cache_file.read_bytes() == cache_bytes_before

    # Confirm subsequent baseline dispatch plan CAN still use ways 9004 & 9021
    g_after, _, _ = road_network_service.get_cached_osm_graph(cache_file)
    assert g_after is not None
    assert any(d.get("osm_way_id") == 9004 for _, _, d in g_after.edges(data=True))

    # Verify idempotent additive SQLite column migration preserves existing rows
    legacy_db_path = tmp_path / "legacy_phase4.db"
    legacy_engine = create_engine(f"sqlite:///{legacy_db_path}")
    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE vehicle_assignments ("
                "id INTEGER PRIMARY KEY, route_coordinates_json JSON NOT NULL)"
            )
        )
        conn.execute(
            text("INSERT INTO vehicle_assignments (id, route_coordinates_json) VALUES (1, '[]')")
        )

    applied_first = ensure_additive_columns(legacy_engine)
    assert "vehicle_assignments.route_geometry_json" in applied_first
    applied_second = ensure_additive_columns(legacy_engine)
    assert applied_second == []

    cols = {c["name"] for c in inspect(legacy_engine).get_columns("vehicle_assignments")}
    assert "route_geometry_json" in cols
    with legacy_engine.connect() as conn:
        row_count = conn.execute(text("SELECT COUNT(*) FROM vehicle_assignments")).scalar()
        assert row_count == 1
    legacy_engine.dispose()
