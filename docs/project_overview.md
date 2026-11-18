# MEDILOGIX — Project Overview

## 1. Purpose & Academic Context

**MEDILOGIX** (*Emergency Medical Supply Distribution Optimization Using Operations Research and Intelligent Decision Support*) is a B.Tech final-year / PBL engineering platform integrating **Operations Research (OR)** and **Data Science / Supply Chain Management (DSCM)**.

During public health emergencies, natural disasters, or sudden trauma surges, regional medical supply chains face simultaneous constraints: limited warehouse inventory, disrupted road corridors, heterogeneous hospital criticality, and fleet capacity limits. MEDILOGIX provides a mathematically rigorous, auditable decision-support workflow to compute optimal supply allocations and delivery routes.

## 2. Geographical Scope

- **Initial Region**: Pune Urban Area and Pimpri-Chinchwad Municipal Corporation (PCMC), Maharashtra, India.
- **Representative Localities**: Pimpri, Shivajinagar, Aundh, Baner, Kothrud, Swargate, Kondhwa, Hadapsar, and Wagholi.
- **Extensibility**: Geographical bounds (`GEO_MIN_LAT`, `GEO_MAX_LAT`, `GEO_MIN_LON`, `GEO_MAX_LON`) are environment-configurable so the platform can scale to the entire Pune district without code changes.

## 3. Core Functional Modules

1. Emergency Command Dashboard
2. Warehouse Management
3. Hospital Management
4. Medical Product Management
5. Inventory Management
6. Hospital Demand Management
7. Transportation Optimization (Multi-Commodity LP)
8. Emergency Priority Management (Lexicographic Shortage Minimization)
9. Delivery Route Optimization (Dijkstra Shortest Path & VRP Extensions)
10. Disaster Scenario Simulator (Warehouse Failure, Road Closure, Demand Surge)
11. Optimization History
12. Performance Analytics and Reports

## 4. Academic Integrity & Synthetic Data Policy

- All warehouse nodes are explicitly labeled as **fictional simulation hubs**.
- Hospital operational profiles, inventories, and demands are **synthetic and reproducible** (`RANDOM_SEED = 42`).
- Coordinates reflect general Pune / PCMC neighborhood centers aligned with OpenStreetMap.
- Route travel times are analytical estimates and do **not** claim to represent live traffic feeds.
- All optimization outputs are computed dynamically via OR solvers (PuLP, NetworkX, Google OR-Tools)—never hardcoded.
