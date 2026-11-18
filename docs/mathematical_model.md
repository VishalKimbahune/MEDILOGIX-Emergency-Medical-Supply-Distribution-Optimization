# MEDILOGIX — Mathematical Formulation & Solver Architecture

This document specifies the Operations Research (OR) models implemented in `backend/app/optimization/` using **PuLP** with the deterministic **COIN-OR CBC** linear programming solver (`PULP_CBC_CMD(msg=False, threads=1)`).

---

## 1. Sets and Indices

- $I$: Set of active medical distribution warehouses, indexed by $i \in I$.
- $J$: Set of active hospitals requiring medical supplies, indexed by $j \in J$, partitioned by emergency priority $P_j$:
  - $J_{\text{crit}} = \{j \in J \mid P_j = \text{critical}\}$
  - $J_{\text{high}} = \{j \in J \mid P_j = \text{high}\}$
  - $J_{\text{norm}} = \{j \in J \mid P_j = \text{normal}\}$
- $K$: Set of essential medical products, indexed by $k \in K$.
- $A = \{(i, j) \in I \times J \mid A_{i,j} = 1\}$: Set of currently open warehouse-to-hospital corridors.

---

## 2. Parameters

- $S_{i,k} \ge 0$: Available net stock (`quantity_available - quantity_reserved`) of product $k$ at warehouse $i$.
- $D_{j,k} \ge 0$: Open / partially fulfilled demand of product $k$ at hospital $j$.
- $C_{i,j,k} \ge 0$: Unit transportation cost of shipping one unit of product $k$ from warehouse $i$ to hospital $j$:
  $$C_{i,j,k} = \text{base\_transport\_cost\_per\_unit}_{i,j} + \text{distance\_km}_{i,j} \times \text{base\_transport\_cost\_per\_km}_{k}$$
- $A_{i,j} \in \{0, 1\}$: Route availability indicator ($1$ if corridor $(i,j)$ exists and is open; $0$ otherwise).
- $w_k > 0$: Unit weight (kg) of product $k$ (for optional route capacity constraints $Q_{i,j}$).

---

## 3. Decision Variables

- $x_{i,j,k} \ge 0$: Planned quantity of product $k$ allocated and transported from warehouse $i$ to hospital $j$ (created only for open routes $(i,j) \in A$).
- $u_{j,k} \ge 0$: Unmet demand (shortage) of product $k$ at hospital $j$.

> **Data Integrity**: Decision variables represent *planned allocations* persisted in `allocations` under an immutable `optimization_runs` record. Solving never mutates original warehouse inventory or hospital demand tables.

---

## 4. Shared Linear Constraints

1. **Warehouse Stock Constraints**:
   $$\sum_{j \in J : (i,j) \in A} x_{i,j,k} \le S_{i,k} \qquad \forall i \in I,\; \forall k \in K$$

2. **Hospital Demand Balance Constraints**:
   $$\sum_{i \in I : (i,j) \in A} x_{i,j,k} + u_{j,k} = D_{j,k} \qquad \forall j \in J,\; \forall k \in K$$

3. **Route Availability Enforcement**:
   $$x_{i,j,k} = 0 \qquad \forall (i,j) \notin A,\; \forall k \in K$$

4. **Non-Negativity**:
   $$x_{i,j,k} \ge 0,\quad u_{j,k} \ge 0 \qquad \forall i \in I,\; j \in J,\; k \in K$$

5. **Optional Route Weight Capacity (when enabled with valid route payload data)**:
   $$\sum_{k \in K} w_k \, x_{i,j,k} \le Q_{i,j} \qquad \forall (i,j) \in A$$

---

## 5. Model A — Multi-Commodity Transportation LP (`transportation.py`)

Priority-neutral baseline minimizing aggregate shortage and transportation cost without arbitrary penalty weights:

- **When `allow_unmet_demand = True` (default)**:
  - **Stage 1**: $\min \; U = \sum_{j \in J} \sum_{k \in K} u_{j,k} \implies U^*$
  - **Stage 2**: $\min \; Z_{\text{cost}} = \sum_{(i,j) \in A} \sum_{k \in K} C_{i,j,k} \, x_{i,j,k}$ subject to $\sum_{j,k} u_{j,k} \le U^* + \varepsilon$ (exact $0$ when $U^* = 0$).
- **When `allow_unmet_demand = False` (strict full fulfillment)**:
  - Fixes $u_{j,k} = 0$ and minimizes $Z_{\text{cost}}$ directly; reports `Infeasible` cleanly if supply or open corridors cannot cover total demand.

---

## 6. Model B — Sequential 4-Stage Lexicographic Priority Optimization (`priority.py`)

Under controlled supply shortages, cost-only transportation LP can starve critical hospitals located farther from distribution hubs. MEDILOGIX resolves this via **strict sequential lexicographic optimization** over normalized unmet-demand fractions.

For each priority tier $P \in \{\text{critical}, \text{high}, \text{normal}\}$, let $D_P = \sum_{j \in J_P} \sum_{k \in K} D_{j,k}$. Whenever $D_P > 0$, define:

$$F_P = \frac{\sum_{j \in J_P} \sum_{k \in K} u_{j,k}}{D_P}$$

*(If $D_P = 0$, the stage is logged as `Skipped (Zero Demand)` with $F_P = 0$ to prevent division by zero.)*

### Sequential Stages

1. **Stage 1 (Critical Hospitals)**:
   $$\min \; F_{\text{crit}} \implies F_{\text{crit}}^*$$
2. **Stage 2 (High-Priority Hospitals)**:
   $$\min \; F_{\text{high}} \quad \text{s.t. } F_{\text{crit}} \le \text{bound}(F_{\text{crit}}^*) \implies F_{\text{high}}^*$$
3. **Stage 3 (Normal-Priority Hospitals)**:
   $$\min \; F_{\text{norm}} \quad \text{s.t. } F_{\text{crit}} \le \text{bound}(F_{\text{crit}}^*),\; F_{\text{high}} \le \text{bound}(F_{\text{high}}^*) \implies F_{\text{norm}}^*$$
4. **Stage 4 (Transportation Cost Minimization)**:
   $$\min \; \sum_{(i,j) \in A} \sum_{k \in K} C_{i,j,k} \, x_{i,j,k}$$
   subject to preserving all three locked priority-tier optimums, where $\text{bound}(f^*) = 0$ if $f^* \le 10^{-9}$ else $f^* + 10^{-8}$.

---

## 7. Verified Sample Results on Baseline Synthetic Dataset (`RANDOM_SEED = 42`)

Executed via PuLP CBC on the seeded 3-warehouse, 8-hospital, 4-product, 24-route Pune & PCMC dataset (`total_demand = 2,611 units`, `total_allocated = 2,422 units`, `total_unmet = 189 units`, `92.76%` overall fulfillment):

| Metric | Multi-Commodity Transportation LP | 4-Stage Lexicographic Priority LP | Difference |
| :--- | :---: | :---: | :---: |
| **Solver Status** | `Optimal` | `Optimal` | — |
| **Total Transport Cost (INR)** | ₹134,932.40 | ₹144,463.31 | +₹9,530.91 (+7.06%) |
| **Critical Tier Fulfillment (913 req.)** | 91.68% (76 unmet) | **100.00% (0 unmet)** | **−76 critical unmet** |
| **High Tier Fulfillment (1,011 req.)** | 89.32% (108 unmet) | **98.71% (13 unmet)** | **−95 high unmet** |
| **Normal Tier Fulfillment (687 req.)** | 99.27% (5 unmet) | 74.38% (176 unmet) | +171 normal unmet |

**Academic Interpretation**: Pure cost optimization leaves 76 Critical and 108 High-priority units unfulfilled while fulfilling 99.27% of cheaper Normal-priority hospitals. Sequential lexicographic optimization guarantees **100% Critical fulfillment** and **98.71% High-priority fulfillment** for a modest 7.06% cost trade-off.

---

## 8. Decoupled Routing Modules (Phase 4 Roadmap)

- **Shortest Path (`shortest_path.py`)**: NetworkX Dijkstra shortest path supporting closed corridor exclusions.
- **Capacitated VRP (`vehicle_routing.py`)**: Google OR-Tools skeleton scheduled for Phase 4.
