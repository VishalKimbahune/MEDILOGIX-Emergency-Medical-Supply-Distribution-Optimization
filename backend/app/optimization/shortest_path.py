"""
Shortest Path Routing Module (NetworkX + Dijkstra).

Kept strictly separate from allocation LP modules. Computes minimum-distance
or minimum-estimated-time paths over a logistics road graph while supporting
edge removals for disaster road-closure simulations.

TODO (Future Phases):
- Ingest actual Pune / PCMC road network graphs from OpenStreetMap via Overpass API.
- Cache processed road graphs under data/processed/.
- Support k-shortest alternative evacuation/delivery corridors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx


@dataclass
class ShortestPathResult:
    """Result returned by Dijkstra shortest-path lookup."""

    source: str
    target: str
    weight_metric: str
    path_nodes: list[str]
    total_weight: float
    reachable: bool
    note: str = "Synthetic corridor estimate; does not represent live traffic."


def build_logistics_graph(
    edges: list[dict[str, Any]],
    closed_edge_codes: set[str] | None = None,
) -> nx.Graph:
    """
    Build an undirected NetworkX graph from route corridor records.

    Each edge dictionary should include:
        route_code, source, target, distance_km, estimated_travel_time_min, is_available
    """
    closed = closed_edge_codes or set()
    graph = nx.Graph()

    for edge in edges:
        if not edge.get("is_available", True):
            continue
        if edge.get("route_code") in closed:
            continue
        graph.add_edge(
            edge["source"],
            edge["target"],
            route_code=edge.get("route_code", ""),
            distance_km=float(edge["distance_km"]),
            estimated_travel_time_min=float(edge["estimated_travel_time_min"]),
        )

    return graph


def compute_shortest_path(
    graph: nx.Graph,
    source: str,
    target: str,
    weight: str = "distance_km",
) -> ShortestPathResult:
    """Compute shortest path between two nodes using Dijkstra's algorithm."""
    if source not in graph or target not in graph:
        return ShortestPathResult(
            source=source,
            target=target,
            weight_metric=weight,
            path_nodes=[],
            total_weight=0.0,
            reachable=False,
            note="Source or target node not found in active graph.",
        )

    try:
        path = nx.dijkstra_path(graph, source=source, target=target, weight=weight)
        total_w = float(nx.dijkstra_path_length(graph, source=source, target=target, weight=weight))
        return ShortestPathResult(
            source=source,
            target=target,
            weight_metric=weight,
            path_nodes=path,
            total_weight=round(total_w, 3),
            reachable=True,
        )
    except nx.NetworkXNoPath:
        return ShortestPathResult(
            source=source,
            target=target,
            weight_metric=weight,
            path_nodes=[],
            total_weight=0.0,
            reachable=False,
            note="No open path exists between source and target under current closures.",
        )
