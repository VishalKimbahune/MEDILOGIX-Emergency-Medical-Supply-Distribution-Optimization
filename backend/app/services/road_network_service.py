"""
Road Network Management & Shortest-Path Service (Phase 5A — Stage 2).

Coordinates:
- Local JSON caching of the Pune & Pimpri-Chinchwad OpenStreetMap directed road graph
- Polite on-demand Overpass API synchronization (never hammering public endpoints)
- Mapping active warehouses and hospitals to road-network vertices & identifying disconnected nodes
- Directed Dijkstra shortest paths with road-closure exclusion and graceful offline fallback
  to the Phase 1-4 synthetic corridor network
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.hospital import Hospital
from app.models.road import Road
from app.models.warehouse import Warehouse
from app.optimization.osm_road_network import (
    OSM_ATTRIBUTION,
    FacilityNodeMapping,
    OSMNetworkMatrix,
    build_osm_distance_time_matrix,
    compute_osm_shortest_path,
    fetch_osm_overpass_data,
    get_largest_strongly_connected_nodes,
    load_graph_cache,
    parse_overpass_to_digraph,
    save_graph_cache,
    snap_facility_to_graph,
    validate_osm_graph,
)
from app.optimization.shortest_path import build_logistics_graph, compute_shortest_path

# Process-level in-memory cache to avoid re-reading JSON on every request
_GRAPH_CACHE: dict[str, Any] = {
    "path": None,
    "mtime": None,
    "graph": None,
    "metadata": None,
    "main_scc": None,
}


def clear_memory_cache() -> None:
    """Reset the in-memory OSM graph cache (useful for testing and forced syncs)."""
    _GRAPH_CACHE["path"] = None
    _GRAPH_CACHE["mtime"] = None
    _GRAPH_CACHE["graph"] = None
    _GRAPH_CACHE["metadata"] = None
    _GRAPH_CACHE["main_scc"] = None


def _resolve_cache_path(override_path: Path | None = None) -> Path:
    if override_path is not None:
        return override_path
    settings = get_settings()
    path = Path(settings.osm_cache_file)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[2] / path).resolve()
    return path


def get_cached_osm_graph_with_diagnostics(
    cache_path: Path | None = None,
) -> tuple[nx.MultiDiGraph | None, dict[str, Any], set[int], str | None]:
    """
    Load and validate the cached directed OSM graph from local disk.

    Returns (graph, metadata, main_scc, fallback_warning). If the cache file is
    missing, corrupted, or fails structural validation, returns (None, {}, set(), reason)
    so callers cleanly activate synthetic fallback.
    """
    resolved = _resolve_cache_path(cache_path)
    if not resolved.exists():
        return (
            None,
            {},
            set(),
            f"Local OSM road-network cache not found at '{resolved.name}'. Activated synthetic corridor fallback.",
        )

    mtime = resolved.stat().st_mtime
    if (
        _GRAPH_CACHE["graph"] is not None
        and _GRAPH_CACHE["path"] == str(resolved)
        and _GRAPH_CACHE["mtime"] == mtime
    ):
        return (
            _GRAPH_CACHE["graph"],
            _GRAPH_CACHE["metadata"] or {},
            _GRAPH_CACHE["main_scc"] or set(),
            None,
        )

    try:
        graph, metadata = load_graph_cache(resolved)
    except Exception as exc:
        return (
            None,
            {},
            set(),
            f"Cached OSM road-network file is invalid or unreadable ({exc}). Activated synthetic corridor fallback.",
        )

    is_valid, invalid_reason = validate_osm_graph(graph)
    if not is_valid:
        return (
            None,
            {},
            set(),
            f"Cached OSM road graph failed validation ({invalid_reason}). Activated synthetic corridor fallback.",
        )

    main_scc = get_largest_strongly_connected_nodes(graph)
    _GRAPH_CACHE["path"] = str(resolved)
    _GRAPH_CACHE["mtime"] = mtime
    _GRAPH_CACHE["graph"] = graph
    _GRAPH_CACHE["metadata"] = metadata
    _GRAPH_CACHE["main_scc"] = main_scc
    return graph, metadata, main_scc, None


def get_cached_osm_graph(
    cache_path: Path | None = None,
) -> tuple[nx.MultiDiGraph | None, dict[str, Any], set[int]]:
    """
    Load the cached directed OSM graph if present and valid on disk; return (None, {}, set())
    cleanly when offline/uncached or invalid rather than raising.
    """
    graph, metadata, main_scc, _ = get_cached_osm_graph_with_diagnostics(cache_path)
    return graph, metadata, main_scc


def build_facility_routing_matrix(
    facilities: list[dict[str, Any]],
    *,
    routing_objective: str = "min_distance",
    closed_way_ids: set[int] | None = None,
    closed_facility_pairs: set[tuple[str, str]] | None = None,
    vehicle_type: str = "medical_truck",
    cache_path: Path | None = None,
    graph_override: nx.MultiDiGraph | nx.DiGraph | None = None,
) -> tuple[str, OSMNetworkMatrix | None, str | None]:
    """
    Build an OSM directed distance/time/geometry matrix for OR-Tools VRP when a valid
    OSM road graph is available; otherwise return ('synthetic_fallback', None, warning).
    """
    settings = get_settings()
    weight_metric = (
        "estimated_travel_time_min" if routing_objective == "min_time" else "distance_km"
    )

    if graph_override is not None:
        is_valid, invalid_reason = validate_osm_graph(graph_override)
        if not is_valid:
            return (
                "synthetic_fallback",
                None,
                f"Provided OSM road graph is invalid ({invalid_reason}). Activated synthetic corridor fallback.",
            )
        graph = graph_override
        metadata: dict[str, Any] = {}
        main_scc = get_largest_strongly_connected_nodes(graph)
    else:
        graph, metadata, main_scc, fallback_warning = get_cached_osm_graph_with_diagnostics(
            cache_path
        )
        if graph is None:
            return "synthetic_fallback", None, fallback_warning

    matrix = build_osm_distance_time_matrix(
        graph,
        facilities=facilities,
        weight_metric=weight_metric,
        closed_way_ids=closed_way_ids,
        closed_facility_pairs=closed_facility_pairs,
        vehicle_type=vehicle_type,
        max_snap_distance_km=settings.osm_max_snap_distance_km,
        main_scc_nodes=main_scc,
        attribution=metadata.get("attribution", OSM_ATTRIBUTION),
    )
    return "osm", matrix, None


def map_facilities_to_osm(
    db: Session,
    graph: nx.DiGraph,
    main_scc: set[int] | None = None,
    max_snap_distance_km: float | None = None,
) -> list[FacilityNodeMapping]:
    """Map all active warehouses and hospitals to nearest accessible OSM nodes."""
    settings = get_settings()
    snap_limit = (
        max_snap_distance_km
        if max_snap_distance_km is not None
        else settings.osm_max_snap_distance_km
    )
    scc = main_scc if main_scc is not None else get_largest_strongly_connected_nodes(graph)

    warehouses = list(
        db.scalars(select(Warehouse).where(Warehouse.status == "active").order_by(Warehouse.code)).all()
    )
    hospitals = list(
        db.scalars(select(Hospital).where(Hospital.status == "active").order_by(Hospital.code)).all()
    )

    mappings: list[FacilityNodeMapping] = []
    for wh in warehouses:
        mappings.append(
            snap_facility_to_graph(
                graph,
                facility_code=wh.code,
                facility_type="warehouse",
                lat=wh.latitude,
                lon=wh.longitude,
                max_snap_distance_km=snap_limit,
                main_scc_nodes=scc,
            )
        )
    for hosp in hospitals:
        mappings.append(
            snap_facility_to_graph(
                graph,
                facility_code=hosp.code,
                facility_type="hospital",
                lat=hosp.latitude,
                lon=hosp.longitude,
                max_snap_distance_km=snap_limit,
                main_scc_nodes=scc,
            )
        )
    return mappings


def get_road_network_status(
    db: Session, cache_path: Path | None = None
) -> dict[str, Any]:
    """Return OSM road-network cache status, graph metrics, attribution, and facility connectivity."""
    settings = get_settings()
    resolved = _resolve_cache_path(cache_path)
    graph, metadata, main_scc = get_cached_osm_graph(resolved)

    if graph is None:
        return {
            "osm_available": False,
            "active_source": "synthetic_fallback",
            "cache_file": str(resolved),
            "attribution": OSM_ATTRIBUTION,
            "node_count": 0,
            "edge_count": 0,
            "oneway_edge_count": 0,
            "largest_scc_node_count": 0,
            "metadata": {},
            "facility_mappings": [],
            "disconnected_facilities": [],
            "note": (
                "No local OSM road-network cache found. Synthetic corridor fallback is active. "
                "Run POST /api/routes/road-network/sync or 'python data/fetch_osm_network.py' to cache Pune OSM roads."
            ),
        }

    mappings = map_facilities_to_osm(db, graph, main_scc=main_scc)
    disconnected = [m.facility_code for m in mappings if not m.is_connected]
    oneway_count = sum(1 for _, _, d in graph.edges(data=True) if d.get("oneway"))

    return {
        "osm_available": True,
        "active_source": "osm_road_network",
        "cache_file": str(resolved),
        "attribution": metadata.get("attribution", OSM_ATTRIBUTION),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "oneway_edge_count": oneway_count,
        "largest_scc_node_count": len(main_scc),
        "metadata": metadata,
        "facility_mappings": [m.__dict__ for m in mappings],
        "disconnected_facilities": disconnected,
        "note": (
            "Directed OSM road geometry loaded from local cache. Travel times are speed-profile "
            "estimates by highway class and do NOT represent live traffic."
        ),
    }


def sync_osm_road_network(
    db: Session,
    force_refresh: bool = False,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """
    Download and cache Pune & Pimpri-Chinchwad OSM road data from Overpass API.

    If a valid cache already exists and force_refresh is False, reuses the cache
    without issuing a network request. If Overpass fails, returns a graceful
    offline fallback status without crashing.
    """
    settings = get_settings()
    resolved = _resolve_cache_path(cache_path)

    if resolved.exists() and not force_refresh:
        status_info = get_road_network_status(db, cache_path=resolved)
        status_info["sync_action"] = "reused_existing_cache"
        return status_info

    bbox = {
        "min_lat": settings.geo_min_lat,
        "max_lat": settings.geo_max_lat,
        "min_lon": settings.geo_min_lon,
        "max_lon": settings.geo_max_lon,
    }

    try:
        raw_payload = fetch_osm_overpass_data(
            min_lat=bbox["min_lat"],
            max_lat=bbox["max_lat"],
            min_lon=bbox["min_lon"],
            max_lon=bbox["max_lon"],
            overpass_url=settings.osm_overpass_url,
            timeout_sec=settings.osm_request_timeout_sec,
            user_agent=settings.osm_user_agent,
        )
        graph = parse_overpass_to_digraph(raw_payload)
        save_graph_cache(
            graph,
            cache_path=resolved,
            bbox=bbox,
            region_name=settings.geo_region_name,
        )
        clear_memory_cache()
        status_info = get_road_network_status(db, cache_path=resolved)
        status_info["sync_action"] = "downloaded_and_cached"
        return status_info
    except Exception as exc:
        fallback = get_road_network_status(db, cache_path=resolved)
        fallback["sync_action"] = "failed_using_fallback"
        fallback["sync_error"] = str(exc)
        return fallback


def _lookup_facility(db: Session, code: str) -> tuple[str, float, float] | None:
    """Resolve a warehouse or hospital code to (facility_type, lat, lon)."""
    wh = db.scalar(select(Warehouse).where(Warehouse.code == code))
    if wh:
        return ("warehouse", float(wh.latitude), float(wh.longitude))
    hosp = db.scalar(select(Hospital).where(Hospital.code == code))
    if hosp:
        return ("hospital", float(hosp.latitude), float(hosp.longitude))
    return None


def compute_facility_shortest_path(
    db: Session,
    source_code: str,
    target_code: str,
    *,
    weight_metric: str = "distance_km",
    closed_way_ids: list[int] | None = None,
    closed_route_codes: list[str] | None = None,
    allow_synthetic_fallback: bool = True,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """
    Compute directed shortest path between two MEDILOGIX facilities.

    Uses cached OpenStreetMap directed road geometry when available and both
    facilities are connected to the main road component; gracefully falls back
    to the synthetic corridor graph if OSM is unavailable or offline.
    """
    src_info = _lookup_facility(db, source_code)
    tgt_info = _lookup_facility(db, target_code)
    if not src_info:
        raise ValueError(f"Unknown facility code '{source_code}'.")
    if not tgt_info:
        raise ValueError(f"Unknown facility code '{target_code}'.")

    closed_ways = {int(w) for w in (closed_way_ids or [])}
    closed_routes = set(closed_route_codes or [])

    # Check if a named synthetic corridor connecting (source, target) was explicitly closed
    warehouses_by_id = {w.id: w for w in db.scalars(select(Warehouse)).all()}
    hospitals_by_id = {h.id: h for h in db.scalars(select(Hospital)).all()}
    roads = list(db.scalars(select(Road)).all())

    corridor_explicitly_closed = False
    for r in roads:
        wc = warehouses_by_id[r.warehouse_id].code if r.warehouse_id in warehouses_by_id else None
        hc = hospitals_by_id[r.hospital_id].code if r.hospital_id in hospitals_by_id else None
        if r.route_code in closed_routes and {wc, hc} == {source_code, target_code}:
            corridor_explicitly_closed = True
            break

    graph, _metadata, main_scc = get_cached_osm_graph(cache_path)
    fallback_reason: str | None = None

    if graph is not None and not corridor_explicitly_closed:
        settings = get_settings()
        src_map = snap_facility_to_graph(
            graph,
            source_code,
            src_info[0],
            src_info[1],
            src_info[2],
            max_snap_distance_km=settings.osm_max_snap_distance_km,
            main_scc_nodes=main_scc,
        )
        tgt_map = snap_facility_to_graph(
            graph,
            target_code,
            tgt_info[0],
            tgt_info[1],
            tgt_info[2],
            max_snap_distance_km=settings.osm_max_snap_distance_km,
            main_scc_nodes=main_scc,
        )

        if src_map.is_connected and tgt_map.is_connected and src_map.osm_node_id and tgt_map.osm_node_id:
            osm_res = compute_osm_shortest_path(
                graph,
                source_node=src_map.osm_node_id,
                target_node=tgt_map.osm_node_id,
                source_code=source_code,
                target_code=target_code,
                weight=weight_metric,
                closed_way_ids=closed_ways,
            )
            if osm_res.reachable or not allow_synthetic_fallback or bool(closed_ways):
                return {
                    **osm_res.__dict__,
                    "source_mapping": src_map.__dict__,
                    "target_mapping": tgt_map.__dict__,
                    "fallback_used": False,
                }
            fallback_reason = osm_res.note
        else:
            fallback_reason = (
                src_map.disconnected_reason
                or tgt_map.disconnected_reason
                or "One or both facilities are disconnected from the OSM road network."
            )
    elif corridor_explicitly_closed:
        fallback_reason = f"Corridor between {source_code} and {target_code} is explicitly closed."
    else:
        fallback_reason = "OSM road-network cache not available locally; using synthetic corridor fallback."

    if not allow_synthetic_fallback:
        return {
            "source_code": source_code,
            "target_code": target_code,
            "source_node": None,
            "target_node": None,
            "weight_metric": weight_metric,
            "reachable": False,
            "source_type": "osm_road_network",
            "distance_km": 0.0,
            "estimated_travel_time_min": 0.0,
            "path_node_ids": [],
            "way_ids": [],
            "road_names": [],
            "geometry": [],
            "attribution": OSM_ATTRIBUTION,
            "fallback_used": False,
            "note": fallback_reason,
        }

    # Graceful fallback to Phase 1-4 synthetic corridor graph
    edges = [
        {
            "route_code": r.route_code,
            "source": warehouses_by_id[r.warehouse_id].code,
            "target": hospitals_by_id[r.hospital_id].code,
            "distance_km": r.distance_km,
            "estimated_travel_time_min": r.estimated_travel_time_min,
            "is_available": r.is_available,
        }
        for r in roads
        if r.warehouse_id in warehouses_by_id and r.hospital_id in hospitals_by_id
    ]
    syn_graph = build_logistics_graph(edges, closed_edge_codes=closed_routes)
    syn_res = compute_shortest_path(syn_graph, source_code, target_code, weight=weight_metric)

    # Build straight-line coordinate list for fallback visualization
    coord_lookup = {w.code: [w.latitude, w.longitude] for w in warehouses_by_id.values()}
    coord_lookup.update({h.code: [h.latitude, h.longitude] for h in hospitals_by_id.values()})
    fallback_geom = [coord_lookup[n] for n in syn_res.path_nodes if n in coord_lookup]

    dist_km = 0.0
    time_min = 0.0
    if syn_res.reachable and len(syn_res.path_nodes) >= 2:
        for idx in range(len(syn_res.path_nodes) - 1):
            edata = syn_graph[syn_res.path_nodes[idx]][syn_res.path_nodes[idx + 1]]
            dist_km += float(edata["distance_km"])
            time_min += float(edata["estimated_travel_time_min"])

    return {
        "source_code": source_code,
        "target_code": target_code,
        "source_node": None,
        "target_node": None,
        "weight_metric": weight_metric,
        "reachable": syn_res.reachable,
        "source_type": "synthetic_fallback",
        "distance_km": round(dist_km, 3),
        "estimated_travel_time_min": round(time_min, 1),
        "path_node_ids": [],
        "path_facility_codes": syn_res.path_nodes,
        "way_ids": [],
        "road_names": [],
        "geometry": fallback_geom,
        "attribution": "Synthetic Pune Corridor Estimate (OSM fallback)",
        "fallback_used": True,
        "fallback_reason": fallback_reason,
        "note": (
            f"Fallback to synthetic corridor network ({fallback_reason}). "
            "Distances and travel times are synthetic estimates; not live traffic."
        ),
    }
