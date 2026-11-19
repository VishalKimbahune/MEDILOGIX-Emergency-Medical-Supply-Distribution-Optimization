"""
OpenStreetMap (OSM) Directed Road-Network Engine (Phase 5A).

Builds a directed NetworkX street graph from OpenStreetMap Overpass API data
for Pune & Pimpri-Chinchwad, preserving real street polyline geometry, edge
lengths, one-way directionality, and delivery-vehicle access restrictions.

Important Notes:
- Attribution: Map and road data © OpenStreetMap contributors (ODbL).
- Road distances are calculated along actual OSM road geometry (segment-by-segment
  Haversine lengths).
- Travel times use assumed urban speed profiles by OSM highway class (or OSM
  maxspeed tags capped for emergency delivery vehicles). They are ESTIMATED
  travel times and do NOT represent live traffic.
- Supports local JSON caching under data/processed/ to respect Overpass API
  fair-use policies and enable reliable offline operation.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import networkx as nx

OSM_ATTRIBUTION: str = "© OpenStreetMap contributors (ODbL 1.0)"

# Road classes accessible to emergency medical delivery vans and trucks
DRIVABLE_HIGHWAY_TYPES: set[str] = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
}

# Assumed average urban delivery speeds (km/h) by OSM highway classification.
# Explicitly estimated; NOT live traffic speeds.
ESTIMATED_SPEED_KMPH_BY_HIGHWAY: dict[str, float] = {
    "motorway": 55.0,
    "motorway_link": 38.0,
    "trunk": 42.0,
    "trunk_link": 32.0,
    "primary": 34.0,
    "primary_link": 26.0,
    "secondary": 28.0,
    "secondary_link": 24.0,
    "tertiary": 24.0,
    "tertiary_link": 20.0,
    "unclassified": 20.0,
    "residential": 18.0,
    "living_street": 12.0,
}

RESTRICTED_ACCESS_VALUES: set[str] = {"no", "private", "military", "forestry", "agricultural"}

OVERPASS_FALLBACK_MIRRORS: tuple[str, ...] = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)


@dataclass
class FacilityNodeMapping:
    """Mapping of a warehouse or hospital coordinate to an OSM road-network node."""

    facility_code: str
    facility_type: str  # warehouse | hospital
    latitude: float
    longitude: float
    osm_node_id: int | None
    snapped_lat: float | None
    snapped_lon: float | None
    snap_distance_km: float | None
    is_connected: bool
    in_main_component: bool = False
    disconnected_reason: str | None = None


@dataclass
class OSMShortestPathResult:
    """Directed shortest-path outcome along the OSM road network."""

    source_code: str
    target_code: str
    source_node: int | None
    target_node: int | None
    weight_metric: str
    reachable: bool
    source_type: str = "osm_road_network"
    distance_km: float = 0.0
    estimated_travel_time_min: float = 0.0
    path_node_ids: list[int] = field(default_factory=list)
    way_ids: list[int] = field(default_factory=list)
    road_names: list[str] = field(default_factory=list)
    geometry: list[list[float]] = field(default_factory=list)  # [[lat, lon], ...]
    attribution: str = OSM_ATTRIBUTION
    note: str = (
        "Calculated on cached OpenStreetMap directed road geometry. "
        "Travel times are speed-profile estimates, not live traffic."
    )


@dataclass
class OSMMatrixLeg:
    """Directed shortest-path leg between two facilities inside an OSM routing matrix."""

    source_code: str
    target_code: str
    reachable: bool
    distance_km: float = 0.0
    estimated_travel_time_min: float = 0.0
    way_ids: list[int] = field(default_factory=list)
    road_names: list[str] = field(default_factory=list)
    geometry: list[list[float]] = field(default_factory=list)
    reason: str | None = None


@dataclass
class OSMNetworkMatrix:
    """Precomputed directed OSM distance, estimated time, and street-geometry matrix."""

    weight_metric: str  # "distance_km" | "estimated_travel_time_min"
    facility_mappings: dict[str, FacilityNodeMapping]
    legs: dict[tuple[str, str], OSMMatrixLeg]
    unreachable_facilities: list[dict[str, Any]] = field(default_factory=list)
    closed_way_ids: list[int] = field(default_factory=list)
    closed_osm_ways: list[dict[str, Any]] = field(default_factory=list)
    attribution: str = OSM_ATTRIBUTION


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers between two WGS84 points."""
    earth_radius_km = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return earth_radius_km * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def polyline_length_km(coords: list[list[float]]) -> float:
    """Compute cumulative geodesic length (km) along a sequence of [lat, lon] points."""
    total = 0.0
    for idx in range(len(coords) - 1):
        lat1, lon1 = coords[idx]
        lat2, lon2 = coords[idx + 1]
        total += haversine_km(lat1, lon1, lat2, lon2)
    return total


def _parse_maxspeed_kmph(raw_speed: str | None) -> float | None:
    """Parse OSM maxspeed tag (e.g. '50', '40 km/h', '30 mph') into km/h."""
    if not raw_speed:
        return None
    text = str(raw_speed).strip().lower()
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    value = float(match.group(1))
    if "mph" in text:
        value *= 1.60934
    if value <= 0 or value > 130:
        return None
    return value


def _is_way_accessible(tags: dict[str, Any], vehicle_class: str = "medical_truck") -> bool:
    """Check whether an OSM way is accessible to emergency medical delivery vehicles."""
    highway = str(tags.get("highway", "")).strip().lower()
    if highway not in DRIVABLE_HIGHWAY_TYPES:
        return False

    access = str(tags.get("access", "")).strip().lower()
    motor_vehicle = str(tags.get("motor_vehicle", "")).strip().lower()
    vehicle = str(tags.get("vehicle", "")).strip().lower()
    hgv = str(tags.get("hgv", "")).strip().lower()
    service = str(tags.get("service", "")).strip().lower()

    if access in RESTRICTED_ACCESS_VALUES:
        return False
    if motor_vehicle in RESTRICTED_ACCESS_VALUES:
        return False
    if vehicle in RESTRICTED_ACCESS_VALUES:
        return False
    if vehicle_class == "medical_truck" and hgv in RESTRICTED_ACCESS_VALUES:
        return False
    if service in {"parking_aisle", "driveway", "alley", "private"}:
        return False

    return True


def _resolve_oneway_direction(tags: dict[str, Any]) -> str:
    """
    Determine edge directionality from OSM tags.

    Returns:
        'forward': only u -> v allowed
        'reverse': only v -> u allowed
        'both':    bidirectional
    """
    oneway = str(tags.get("oneway", "")).strip().lower()
    highway = str(tags.get("highway", "")).strip().lower()
    junction = str(tags.get("junction", "")).strip().lower()

    if oneway in {"yes", "1", "true"}:
        return "forward"
    if oneway in {"-1", "reverse"}:
        return "reverse"
    if oneway in {"no", "0", "false"}:
        return "both"
    if highway in {"motorway", "motorway_link"} or junction in {"roundabout", "circular"}:
        return "forward"
    return "both"


def _estimate_edge_speed_kmph(tags: dict[str, Any]) -> float:
    """Compute conservative urban delivery speed estimate (km/h) for an OSM way."""
    highway = str(tags.get("highway", "unclassified")).strip().lower()
    default_speed = ESTIMATED_SPEED_KMPH_BY_HIGHWAY.get(highway, 22.0)
    parsed_limit = _parse_maxspeed_kmph(tags.get("maxspeed"))
    if parsed_limit is not None:
        # Cap assumed urban delivery speed at 85% of posted maxspeed and <= 60 km/h
        return round(min(60.0, max(10.0, min(default_speed * 1.15, parsed_limit * 0.85))), 1)
    return default_speed


def parse_overpass_to_digraph(
    overpass_payload: dict[str, Any],
    vehicle_class: str = "medical_truck",
) -> nx.MultiDiGraph:
    """
    Convert an Overpass API JSON payload into a directed MultiDiGraph road network.

    Splits OSM ways at intersection vertices so:
    - Every street intersection is a graph node.
    - Parallel roads between the same two intersections (e.g., flyovers, service
      roads, or alternate arterials) are preserved as distinct keyed edges so
      closing one OSM way still allows rerouting via parallel open roads.
    - Every directed edge preserves full intermediate OSM street geometry,
      exact geodesic length, one-way rules, and road metadata.
    """
    elements = overpass_payload.get("elements", [])
    nodes_coords: dict[int, tuple[float, float]] = {}
    raw_ways: list[dict[str, Any]] = []

    for elem in elements:
        etype = elem.get("type")
        if etype == "node" and "lat" in elem and "lon" in elem:
            nodes_coords[int(elem["id"])] = (float(elem["lat"]), float(elem["lon"]))
        elif etype == "way":
            tags = elem.get("tags") or {}
            if _is_way_accessible(tags, vehicle_class=vehicle_class):
                raw_ways.append(elem)

    # Count how many ways reference each node to identify intersections
    node_usage: Counter[int] = Counter()
    for way in raw_ways:
        w_nodes = [int(n) for n in way.get("nodes", []) if int(n) in nodes_coords]
        if len(w_nodes) < 2:
            continue
        for nid in w_nodes:
            node_usage[nid] += 1
        # Endpoints are always topological vertices
        node_usage[w_nodes[0]] += 1
        node_usage[w_nodes[-1]] += 1

    graph = nx.MultiDiGraph()

    def _add_directed_edge(
        u: int,
        v: int,
        geom: list[list[float]],
        dist_km: float,
        time_min: float,
        attrs: dict[str, Any],
    ) -> None:
        if u == v:
            return
        edge_key = int(attrs["osm_way_id"])
        if graph.has_edge(u, v, key=edge_key) and graph[u][v][edge_key]["distance_km"] <= dist_km:
            return
        graph.add_edge(
            u,
            v,
            key=edge_key,
            distance_km=round(dist_km, 4),
            estimated_travel_time_min=round(time_min, 2),
            geometry=geom,
            **attrs,
        )

    for way in raw_ways:
        tags = way.get("tags") or {}
        way_id = int(way["id"])
        w_nodes = [int(n) for n in way.get("nodes", []) if int(n) in nodes_coords]
        if len(w_nodes) < 2:
            continue

        direction = _resolve_oneway_direction(tags)
        highway = str(tags.get("highway", "unclassified")).strip().lower()
        road_name = str(tags.get("name") or tags.get("ref") or f"Unnamed {highway} road")
        speed_kmph = _estimate_edge_speed_kmph(tags)
        maxspeed = _parse_maxspeed_kmph(tags.get("maxspeed"))

        # Split way into segments between intersection vertices
        seg_start = 0
        for idx in range(1, len(w_nodes)):
            is_endpoint = idx == len(w_nodes) - 1
            is_intersection = node_usage[w_nodes[idx]] > 1
            if not (is_endpoint or is_intersection):
                continue

            sub_nodes = w_nodes[seg_start : idx + 1]
            u, v = sub_nodes[0], sub_nodes[-1]
            geom_fwd = [
                [round(nodes_coords[n][0], 6), round(nodes_coords[n][1], 6)] for n in sub_nodes
            ]
            dist_km = max(0.005, polyline_length_km(geom_fwd))
            time_min = max(0.1, (dist_km / speed_kmph) * 60.0)

            for endpoint_id in (u, v):
                if endpoint_id not in graph:
                    lat, lon = nodes_coords[endpoint_id]
                    graph.add_node(endpoint_id, lat=round(lat, 6), lon=round(lon, 6))

            hgv_tag = str(tags.get("hgv", "")).strip().lower()
            edge_attrs = {
                "osm_way_id": way_id,
                "name": road_name,
                "highway": highway,
                "oneway": direction != "both",
                "direction_rule": direction,
                "maxspeed_kmph": maxspeed,
                "estimated_speed_kmph": speed_kmph,
                "vehicle_accessible": True,
                "hgv_restricted": hgv_tag in RESTRICTED_ACCESS_VALUES,
            }

            if direction in {"forward", "both"}:
                _add_directed_edge(u, v, geom_fwd, dist_km, time_min, edge_attrs)
            if direction in {"reverse", "both"}:
                geom_rev = list(reversed(geom_fwd))
                _add_directed_edge(v, u, geom_rev, dist_km, time_min, edge_attrs)

            seg_start = idx

    return graph


def build_overpass_road_query(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    include_minor: bool = False,
) -> str:
    """
    Build a compact Overpass QL query for drivable Pune & PCMC arterial/collector roads.

    Uses Overpass's official lightweight pattern (`out body; >; out skel qt;`)
    so way tags (name, highway, oneway, maxspeed, access) are preserved while
    node geometry stays compact and fast to download within public fair-use limits.
    """
    highway_regex = (
        "^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|"
        "secondary|secondary_link|tertiary|tertiary_link"
        + ("|unclassified|residential)$" if include_minor else ")$")
    )
    bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    return (
        f"[out:json][timeout:60];\n"
        f"(\n"
        f'  way["highway"~"{highway_regex}"]({bbox});\n'
        f");\n"
        f"out body;\n"
        f">;\n"
        f"out skel qt;\n"
    )


def fetch_osm_overpass_data(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    overpass_url: str | None = None,
    timeout_sec: int = 45,
    user_agent: str = "MEDILOGIX-Academic-OR-Prototype/1.0",
) -> dict[str, Any]:
    """
    Fetch OpenStreetMap road data from Overpass API with polite headers and mirror fallback.

    Raises RuntimeError if all endpoints fail or return invalid payloads.
    """
    query = build_overpass_road_query(min_lat, max_lat, min_lon, max_lon)
    urls = [overpass_url] if overpass_url else []
    for mirror in OVERPASS_FALLBACK_MIRRORS:
        if mirror not in urls:
            urls.append(mirror)

    errors: list[str] = []
    headers = {"User-Agent": user_agent, "Accept": "application/json"}

    for url in urls:
        try:
            with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
                resp = client.post(url, data={"data": query}, headers=headers)
                resp.raise_for_status()
                payload = resp.json()
                if "elements" in payload and len(payload["elements"]) > 0:
                    return payload
                errors.append(f"{url}: empty elements payload")
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    raise RuntimeError("Overpass API download failed across endpoints: " + " | ".join(errors))


def save_graph_cache(
    graph: nx.DiGraph,
    cache_path: Path,
    bbox: dict[str, float],
    region_name: str = "Pune Urban & Pimpri-Chinchwad",
) -> dict[str, Any]:
    """Persist directed OSM road graph with geometry and attribution metadata to JSON."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "region_name": region_name,
        "bbox": bbox,
        "attribution": OSM_ATTRIBUTION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "speed_model_note": (
            "Edge distances use OSM road geometry; travel times use assumed speed "
            "profiles by highway class and do NOT represent live traffic."
        ),
    }

    payload = {
        "metadata": metadata,
        "nodes": [
            {"id": int(nid), "lat": float(data["lat"]), "lon": float(data["lon"])}
            for nid, data in graph.nodes(data=True)
        ],
        "edges": [
            {
                "u": int(u),
                "v": int(v),
                "osm_way_id": data.get("osm_way_id"),
                "name": data.get("name"),
                "highway": data.get("highway"),
                "oneway": bool(data.get("oneway", False)),
                "direction_rule": data.get("direction_rule", "both"),
                "maxspeed_kmph": data.get("maxspeed_kmph"),
                "estimated_speed_kmph": data.get("estimated_speed_kmph"),
                "distance_km": float(data["distance_km"]),
                "estimated_travel_time_min": float(data["estimated_travel_time_min"]),
                "vehicle_accessible": bool(data.get("vehicle_accessible", True)),
                "hgv_restricted": bool(data.get("hgv_restricted", False)),
                "geometry": data.get("geometry", []),
            }
            for u, v, data in graph.edges(data=True)
        ],
    }

    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    return metadata


def load_graph_cache(cache_path: Path) -> tuple[nx.MultiDiGraph, dict[str, Any]]:
    """Load cached directed OSM MultiDiGraph and metadata from local disk."""
    if not cache_path.exists():
        raise FileNotFoundError(f"OSM road-network cache not found at {cache_path}")

    with cache_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    graph = nx.MultiDiGraph()
    for node in payload.get("nodes", []):
        graph.add_node(int(node["id"]), lat=float(node["lat"]), lon=float(node["lon"]))

    for idx, edge in enumerate(payload.get("edges", [])):
        edge_key = int(edge["osm_way_id"]) if edge.get("osm_way_id") is not None else idx
        graph.add_edge(
            int(edge["u"]),
            int(edge["v"]),
            key=edge_key,
            osm_way_id=edge.get("osm_way_id"),
            name=edge.get("name"),
            highway=edge.get("highway"),
            oneway=bool(edge.get("oneway", False)),
            direction_rule=edge.get("direction_rule", "both"),
            maxspeed_kmph=edge.get("maxspeed_kmph"),
            estimated_speed_kmph=edge.get("estimated_speed_kmph"),
            distance_km=float(edge["distance_km"]),
            estimated_travel_time_min=float(edge["estimated_travel_time_min"]),
            vehicle_accessible=bool(edge.get("vehicle_accessible", True)),
            hgv_restricted=bool(edge.get("hgv_restricted", False)),
            geometry=edge.get("geometry", []),
        )

    return graph, payload.get("metadata", {})


def get_largest_strongly_connected_nodes(graph: nx.DiGraph) -> set[int]:
    """Return node IDs belonging to the largest strongly connected component."""
    if graph.number_of_nodes() == 0:
        return set()
    largest = max(nx.strongly_connected_components(graph), key=len)
    return set(largest)


def snap_facility_to_graph(
    graph: nx.DiGraph,
    facility_code: str,
    facility_type: str,
    lat: float,
    lon: float,
    max_snap_distance_km: float = 2.5,
    main_scc_nodes: set[int] | None = None,
) -> FacilityNodeMapping:
    """
    Map a warehouse or hospital coordinate to the nearest accessible OSM graph node.

    Prefers nodes inside the largest strongly connected component (so vehicles can
    both reach and return from the facility). Flags facilities exceeding
    max_snap_distance_km or outside the main component cleanly.
    """
    if graph.number_of_nodes() == 0:
        return FacilityNodeMapping(
            facility_code=facility_code,
            facility_type=facility_type,
            latitude=lat,
            longitude=lon,
            osm_node_id=None,
            snapped_lat=None,
            snapped_lon=None,
            snap_distance_km=None,
            is_connected=False,
            in_main_component=False,
            disconnected_reason="OSM road graph is empty.",
        )

    scc = main_scc_nodes if main_scc_nodes is not None else get_largest_strongly_connected_nodes(graph)

    def _find_nearest(candidate_nodes: set[int] | None) -> tuple[int | None, float]:
        best_id: int | None = None
        best_dist = float("inf")
        for nid, data in graph.nodes(data=True):
            if candidate_nodes is not None and nid not in candidate_nodes:
                continue
            d = haversine_km(lat, lon, float(data["lat"]), float(data["lon"]))
            if d < best_dist:
                best_dist = d
                best_id = int(nid)
        return best_id, best_dist

    # First search within the largest strongly connected component
    best_scc_node, best_scc_dist = _find_nearest(scc if scc else None)
    if best_scc_node is not None and best_scc_dist <= max_snap_distance_km:
        ndata = graph.nodes[best_scc_node]
        return FacilityNodeMapping(
            facility_code=facility_code,
            facility_type=facility_type,
            latitude=lat,
            longitude=lon,
            osm_node_id=best_scc_node,
            snapped_lat=float(ndata["lat"]),
            snapped_lon=float(ndata["lon"]),
            snap_distance_km=round(best_scc_dist, 4),
            is_connected=True,
            in_main_component=True,
        )

    # Otherwise check entire graph to diagnose whether facility is isolated or too far
    any_node, any_dist = _find_nearest(None)
    if any_node is None or any_dist > max_snap_distance_km:
        return FacilityNodeMapping(
            facility_code=facility_code,
            facility_type=facility_type,
            latitude=lat,
            longitude=lon,
            osm_node_id=None,
            snapped_lat=None,
            snapped_lon=None,
            snap_distance_km=round(any_dist, 4) if any_node is not None else None,
            is_connected=False,
            in_main_component=False,
            disconnected_reason=(
                f"Nearest OSM road node is {any_dist:.2f} km away "
                f"(exceeds max snap threshold {max_snap_distance_km:.2f} km)."
            ),
        )

    ndata = graph.nodes[any_node]
    return FacilityNodeMapping(
        facility_code=facility_code,
        facility_type=facility_type,
        latitude=lat,
        longitude=lon,
        osm_node_id=any_node,
        snapped_lat=float(ndata["lat"]),
        snapped_lon=float(ndata["lon"]),
        snap_distance_km=round(any_dist, 4),
        is_connected=False,
        in_main_component=False,
        disconnected_reason="Snapped node lies outside the main strongly connected road component.",
    )


def validate_osm_graph(graph: Any) -> tuple[bool, str | None]:
    """
    Validate that an OSM graph object is a usable directed road network.

    Checks structural type, non-empty nodes/edges, valid numeric WGS84 coordinates,
    and positive numeric edge distance_km & estimated_travel_time_min weights.
    """
    if not isinstance(graph, (nx.DiGraph, nx.MultiDiGraph)):
        return False, "OSM graph object is not a directed NetworkX graph."
    if graph.number_of_nodes() < 2 or graph.number_of_edges() < 1:
        return False, "OSM road graph is empty or lacks drivable road edges."

    for nid, data in graph.nodes(data=True):
        try:
            lat = float(data["lat"])
            lon = float(data["lon"])
        except (KeyError, TypeError, ValueError):
            return False, f"OSM node {nid} is missing valid numeric lat/lon coordinates."
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return False, f"OSM node {nid} has out-of-range coordinates ({lat}, {lon})."

    for u, v, data in graph.edges(data=True):
        try:
            dist = float(data["distance_km"])
            t_min = float(data["estimated_travel_time_min"])
        except (KeyError, TypeError, ValueError):
            return False, f"OSM edge ({u}->{v}) is missing numeric distance_km/estimated_travel_time_min."
        if not (math.isfinite(dist) and dist > 0 and math.isfinite(t_min) and t_min > 0):
            return False, f"OSM edge ({u}->{v}) has non-positive or non-finite weight."

    return True, None


def _build_filtered_graph(
    graph: nx.MultiDiGraph | nx.DiGraph,
    *,
    closed_way_ids: set[int] | None = None,
    closed_edges: set[tuple[int, int]] | None = None,
    vehicle_type: str = "medical_truck",
) -> nx.MultiDiGraph | nx.DiGraph:
    """
    Return an isolated read-only subgraph view excluding closed OSM ways/edges
    and edges inaccessible to the requested vehicle class (never mutates graph).
    """
    blocked_ways = closed_way_ids or set()
    blocked_edges = closed_edges or set()
    enforce_truck = str(vehicle_type).strip().lower() == "medical_truck"

    # Fast path: when no closures are active and graph has no restricted edges,
    # bypass subgraph_view Python callback overhead (5x-8x faster Dijkstra).
    if not blocked_ways and not blocked_edges:
        has_restricted = graph.graph.get("_has_restricted_edges")
        if has_restricted is None:
            has_restricted = any(
                d.get("vehicle_accessible", True) is False
                or d.get("hgv_restricted", False) is True
                for _, _, d in graph.edges(data=True)
            )
            graph.graph["_has_restricted_edges"] = has_restricted
        if not has_restricted:
            return graph

    def _edge_allowed(u: int, v: int, edata: dict[str, Any]) -> bool:
        if (u, v) in blocked_edges:
            return False
        if edata.get("vehicle_accessible", True) is False:
            return False
        if enforce_truck and edata.get("hgv_restricted", False) is True:
            return False
        way_id = edata.get("osm_way_id")
        if way_id is not None and int(way_id) in blocked_ways:
            return False
        return True

    if graph.is_multigraph():
        return nx.subgraph_view(
            graph,
            filter_edge=lambda u, v, k: _edge_allowed(u, v, graph[u][v][k]),
        )
    return nx.subgraph_view(
        graph,
        filter_edge=lambda u, v: _edge_allowed(u, v, graph[u][v]),
    )


def _reconstruct_path_metrics(
    graph: nx.MultiDiGraph | nx.DiGraph,
    active_graph: nx.MultiDiGraph | nx.DiGraph,
    path_nodes: list[int],
    weight: str,
) -> tuple[float, float, list[int], list[str], list[list[float]]]:
    """Sum distance_km, estimated_travel_time_min, way_ids, road_names, and polyline geometry."""
    is_multi = graph.is_multigraph()
    total_dist = 0.0
    total_time = 0.0
    geometry: list[list[float]] = []
    way_ids: list[int] = []
    road_names: list[str] = []

    if len(path_nodes) == 1:
        nd = graph.nodes[path_nodes[0]]
        return 0.0, 0.0, [], [], [[float(nd["lat"]), float(nd["lon"])]]

    for idx in range(len(path_nodes) - 1):
        u, v = path_nodes[idx], path_nodes[idx + 1]
        if is_multi:
            edge_dict = active_graph.get_edge_data(u, v) or {}
            edata = min(edge_dict.values(), key=lambda d: float(d.get(weight, float("inf"))))
        else:
            edata = active_graph[u][v]

        total_dist += float(edata["distance_km"])
        total_time += float(edata["estimated_travel_time_min"])

        wid = edata.get("osm_way_id")
        if wid is not None and (not way_ids or way_ids[-1] != int(wid)):
            way_ids.append(int(wid))

        rname = edata.get("name")
        if rname and (not road_names or road_names[-1] != rname):
            road_names.append(str(rname))

        seg_geom = edata.get("geometry") or [
            [float(graph.nodes[u]["lat"]), float(graph.nodes[u]["lon"])],
            [float(graph.nodes[v]["lat"]), float(graph.nodes[v]["lon"])],
        ]
        if geometry and seg_geom and geometry[-1] == seg_geom[0]:
            geometry.extend(seg_geom[1:])
        else:
            geometry.extend(seg_geom)

    return round(total_dist, 3), round(total_time, 1), way_ids, road_names, geometry


def compute_osm_shortest_path(
    graph: nx.MultiDiGraph | nx.DiGraph,
    source_node: int,
    target_node: int,
    *,
    source_code: str = "",
    target_code: str = "",
    weight: str = "distance_km",
    closed_way_ids: set[int] | None = None,
    closed_edges: set[tuple[int, int]] | None = None,
    vehicle_type: str = "medical_truck",
) -> OSMShortestPathResult:
    """
    Compute directed Dijkstra shortest path along the OSM road graph while
    respecting one-way edges, vehicle access restrictions, and closed OSM ways.
    """
    if source_node not in graph or target_node not in graph:
        return OSMShortestPathResult(
            source_code=source_code,
            target_code=target_code,
            source_node=source_node,
            target_node=target_node,
            weight_metric=weight,
            reachable=False,
            note="Source or target node not present in OSM road graph.",
        )

    active_graph = _build_filtered_graph(
        graph,
        closed_way_ids=closed_way_ids,
        closed_edges=closed_edges,
        vehicle_type=vehicle_type,
    )

    try:
        path_nodes = nx.dijkstra_path(active_graph, source=source_node, target=target_node, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return OSMShortestPathResult(
            source_code=source_code,
            target_code=target_code,
            source_node=source_node,
            target_node=target_node,
            weight_metric=weight,
            reachable=False,
            note="No directed open OSM road path exists between source and target under current restrictions/closures.",
        )

    total_dist, total_time, way_ids, road_names, geometry = _reconstruct_path_metrics(
        graph, active_graph, path_nodes, weight
    )

    return OSMShortestPathResult(
        source_code=source_code,
        target_code=target_code,
        source_node=source_node,
        target_node=target_node,
        weight_metric=weight,
        reachable=True,
        source_type="osm_road_network",
        distance_km=total_dist,
        estimated_travel_time_min=total_time,
        path_node_ids=[int(n) for n in path_nodes],
        way_ids=way_ids,
        road_names=road_names,
        geometry=geometry,
    )


def extract_closed_ways_geometry(
    graph: nx.MultiDiGraph | nx.DiGraph,
    closed_way_ids: set[int] | None,
) -> list[dict[str, Any]]:
    """
    Extract street polyline segments for closed OSM way IDs so the frontend map
    can highlight closed roads directly on the Pune street network.
    """
    if not closed_way_ids:
        return []

    grouped: dict[int, dict[str, Any]] = {}
    seen_segments: set[tuple[int, tuple[float, float], tuple[float, float]]] = set()

    for u, v, data in graph.edges(data=True):
        wid = data.get("osm_way_id")
        if wid is None or int(wid) not in closed_way_ids:
            continue
        wid_int = int(wid)
        geom = data.get("geometry") or [
            [float(graph.nodes[u]["lat"]), float(graph.nodes[u]["lon"])],
            [float(graph.nodes[v]["lat"]), float(graph.nodes[v]["lon"])],
        ]
        if len(geom) < 2:
            continue
        # Deduplicate reverse-direction copies of bidirectional edges on map display
        p_start = (round(geom[0][0], 5), round(geom[0][1], 5))
        p_end = (round(geom[-1][0], 5), round(geom[-1][1], 5))
        canon = (wid_int, min(p_start, p_end), max(p_start, p_end))
        if canon in seen_segments:
            continue
        seen_segments.add(canon)

        if wid_int not in grouped:
            grouped[wid_int] = {
                "way_id": wid_int,
                "name": str(data.get("name") or f"OSM Way {wid_int}"),
                "highway": str(data.get("highway") or "road"),
                "segments": [],
            }
        grouped[wid_int]["segments"].append(geom)

    return [grouped[wid] for wid in sorted(grouped.keys())]


def build_osm_distance_time_matrix(
    graph: nx.MultiDiGraph | nx.DiGraph,
    facilities: list[dict[str, Any]],
    *,
    weight_metric: str = "distance_km",
    closed_way_ids: set[int] | None = None,
    closed_facility_pairs: set[tuple[str, str]] | None = None,
    vehicle_type: str = "medical_truck",
    max_snap_distance_km: float = 2.5,
    main_scc_nodes: set[int] | None = None,
    attribution: str = OSM_ATTRIBUTION,
) -> OSMNetworkMatrix:
    """
    Build a directed all-pairs OSM road-network distance, estimated travel time,
    and street-geometry matrix for a set of warehouses and hospitals.

    Uses one single-source Dijkstra pass per unique facility over an isolated
    filtered subgraph view (never mutating the cached OSM graph). Unreachable
    pairs are explicitly marked reachable=False and are NEVER silently replaced
    by synthetic distances.
    """
    blocked_ways = {int(w) for w in (closed_way_ids or set())}
    blocked_pairs = closed_facility_pairs or set()
    scc = main_scc_nodes if main_scc_nodes is not None else get_largest_strongly_connected_nodes(graph)

    # Deduplicate facilities by code preserving deterministic order
    unique_facilities: dict[str, dict[str, Any]] = {}
    for fac in facilities:
        code = str(fac["code"])
        if code not in unique_facilities:
            unique_facilities[code] = fac

    facility_mappings: dict[str, FacilityNodeMapping] = {}
    unreachable_facilities: list[dict[str, Any]] = []

    for code, fac in unique_facilities.items():
        mapping = snap_facility_to_graph(
            graph,
            facility_code=code,
            facility_type=str(fac.get("type", "hospital")),
            lat=float(fac["lat"]),
            lon=float(fac["lon"]),
            max_snap_distance_km=max_snap_distance_km,
            main_scc_nodes=scc,
        )
        facility_mappings[code] = mapping
        if mapping.osm_node_id is None:
            unreachable_facilities.append(
                {
                    "facility_code": code,
                    "facility_type": mapping.facility_type,
                    "reason": mapping.disconnected_reason or "Failed to snap to OSM road network.",
                }
            )

    active_graph = _build_filtered_graph(
        graph,
        closed_way_ids=blocked_ways,
        vehicle_type=vehicle_type,
    )

    legs: dict[tuple[str, str], OSMMatrixLeg] = {}
    codes = list(unique_facilities.keys())

    for src_code in codes:
        src_map = facility_mappings[src_code]
        src_fac = unique_facilities[src_code]
        src_node = src_map.osm_node_id

        paths_by_target: dict[int, list[int]] = {}
        if src_node is not None and src_node in active_graph:
            try:
                _, paths_by_target = nx.single_source_dijkstra(
                    active_graph, source=src_node, weight=weight_metric
                )
            except nx.NodeNotFound:
                paths_by_target = {}

        for tgt_code in codes:
            if src_code == tgt_code:
                continue
            tgt_map = facility_mappings[tgt_code]
            tgt_fac = unique_facilities[tgt_code]
            tgt_node = tgt_map.osm_node_id

            if (src_code, tgt_code) in blocked_pairs or (tgt_code, src_code) in blocked_pairs:
                legs[(src_code, tgt_code)] = OSMMatrixLeg(
                    source_code=src_code,
                    target_code=tgt_code,
                    reachable=False,
                    reason=f"Road corridor between {src_code} and {tgt_code} is closed.",
                )
                continue

            if src_node is None:
                legs[(src_code, tgt_code)] = OSMMatrixLeg(
                    source_code=src_code,
                    target_code=tgt_code,
                    reachable=False,
                    reason=src_map.disconnected_reason or f"Origin {src_code} could not snap to OSM road network.",
                )
                continue

            if tgt_node is None:
                legs[(src_code, tgt_code)] = OSMMatrixLeg(
                    source_code=src_code,
                    target_code=tgt_code,
                    reachable=False,
                    reason=tgt_map.disconnected_reason or f"Destination {tgt_code} could not snap to OSM road network.",
                )
                continue

            path_nodes = paths_by_target.get(tgt_node)
            if not path_nodes:
                legs[(src_code, tgt_code)] = OSMMatrixLeg(
                    source_code=src_code,
                    target_code=tgt_code,
                    reachable=False,
                    reason=(
                        f"No open directed OSM road path from {src_code} to {tgt_code} "
                        f"under current one-way, vehicle-access, and closure rules."
                    ),
                )
                continue

            dist_km, time_min, way_ids, road_names, road_geom = _reconstruct_path_metrics(
                graph, active_graph, path_nodes, weight_metric
            )

            # Anchor polyline cleanly to exact facility marker coordinates at endpoints
            src_pt = [round(float(src_fac["lat"]), 6), round(float(src_fac["lon"]), 6)]
            tgt_pt = [round(float(tgt_fac["lat"]), 6), round(float(tgt_fac["lon"]), 6)]
            full_geom: list[list[float]] = [src_pt]
            for pt in road_geom:
                if full_geom[-1] != pt:
                    full_geom.append(pt)
            if full_geom[-1] != tgt_pt:
                full_geom.append(tgt_pt)

            legs[(src_code, tgt_code)] = OSMMatrixLeg(
                source_code=src_code,
                target_code=tgt_code,
                reachable=True,
                distance_km=dist_km,
                estimated_travel_time_min=time_min,
                way_ids=way_ids,
                road_names=road_names,
                geometry=full_geom,
            )

    closed_osm_ways = extract_closed_ways_geometry(graph, blocked_ways)

    return OSMNetworkMatrix(
        weight_metric=weight_metric,
        facility_mappings=facility_mappings,
        legs=legs,
        unreachable_facilities=unreachable_facilities,
        closed_way_ids=sorted(blocked_ways),
        closed_osm_ways=closed_osm_ways,
        attribution=attribution,
    )
